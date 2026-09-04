"""
Chunk-driven color deconvolution + collagen segmentation, reading directly
from a multiresolution OME-Zarr (produced by czi_to_zarr.py) instead of the
raw CZI.

Design:
  - Tissue mask and the multi-Otsu threshold are computed once from the
    COARSEST pyramid level (cheap, whole-slide-representative) rather than
    full resolution.
  - Color deconvolution and thresholding run chunk-by-chunk at a caller-
    chosen TARGET resolution (--scaling, same semantics as decon.py: 1 =
    full res, 2 = half res, ...), so the target-resolution image is never
    materialized in memory as a single array -- only one chunk at a time.
  - The low-res tissue mask is mapped onto each chunk by cropping+upsampling
    just that chunk's footprint (never the whole mask at target resolution
    at once), for the same memory-safety reason.
  - Chunk read+decon+threshold (CPU-bound) is parallelized across worker
    processes; all zarr writes stay serialized on the main process to avoid
    a cross-process shard read-modify-write race (same pattern as
    stream_czi_to_ome_zarr's tile ingestion).

Outputs (plain, single-resolution Zarr v3 arrays, not multiscale pyramids --
these are analysis outputs at one fixed working resolution, not raw data
that benefits from multi-zoom access). Written as named children of the same
data.zarr store the input "raw" group lives in (one zarr store per sample,
rather than a separate top-level .zarr directory per array):
    <output_dir>/data.zarr/psr        deconvolved PSR channel
    <output_dir>/data.zarr/mask       tissue mask
    <output_dir>/data.zarr/collagen   binary collagen segmentation
    <output_dir>/res.csv              per-chunk collagen/tissue area (matches
                                       seg.py's tiled res.csv columns)
"""
import argparse
import json
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
import zarr
from tqdm.auto import tqdm

from pyHisto.utils import is_valid_file_or_directory, get_tissue_mask, log, ensure_zarr_root_group
from pyHisto.zarr_pipeline import (
    _decon_seg_one_region,
    _init_decon_seg_worker,
    compute_masked_multiotsu_threshold,
    crop_and_resize_mask_for_region,
    deconvolve_chunk,
    iter_chunk_regions,
    pick_pyramid_level,
    threshold_chunk,
)


def get_args():
    parser = argparse.ArgumentParser(prog="decon_seg_zarr",
                                      description="Chunk-driven decon+seg directly from an OME-Zarr pyramid")
    parser.add_argument("-i", "--input", dest="input", required=True, metavar="PATH",
                         type=is_valid_file_or_directory,
                         help="Path to the input raw group (e.g. <sample>/data.zarr/raw)")
    parser.add_argument("-o", "--output-dir", dest="output_dir", required=True, metavar="DIR",
                         help="Sample output directory; writes data.zarr/{psr,mask,collagen} and res.csv into it")
    parser.add_argument("--stain_map", dest="stain_map", required=True, metavar="PATH",
                         help="Path of the stain vector map JSON file")
    parser.add_argument("-s", "--scaling", dest="scaling", default=1, type=float, metavar="FLOAT",
                         help="Target downsampling factor (1 = full res), matched to the closest pyramid level")
    parser.add_argument("--classes", dest="classes", default=4, type=int, metavar="INT",
                         help="Number of classes for multi-level Otsu thresholding")
    parser.add_argument("-c", "--class", dest="class_id", default=0, type=int, metavar="INT",
                         help="Selected threshold class ID (0 matches seg.py's default and the verified 2023 run)")
    parser.add_argument("--no-parallel", dest="parallel", action="store_false", default=True,
                         help="Disable parallel chunk processing (default: parallel enabled)")
    parser.add_argument("--n-workers", dest="n_workers", default=None, type=int, metavar="INT",
                         help="Number of worker processes (default: min(cpu_count(), 8))")
    return parser.parse_args()


def _read_level_scales(root):
    """Per-level Y-axis scale factor relative to level 0, from OME multiscales metadata."""
    datasets = root.attrs["ome"]["multiscales"][0]["datasets"]
    return [ds["coordinateTransformations"][0]["scale"][-2] for ds in datasets]


def _to_hwc(czyx_array):
    """(C, 1, H, W) -> (H, W, C), squeezing the singleton Z axis."""
    return np.transpose(czyx_array[:, 0, :, :], (1, 2, 0))


def main(args):
    with open(args.stain_map if args.stain_map.endswith(".json") else args.stain_map + ".json") as f:
        stain_color_map = json.load(f)
    stains = list(stain_color_map.keys())
    stain_matrix = np.array([stain_color_map[s] for s in stains]).T

    root = zarr.open_group(args.input, mode="r")
    level_scales = _read_level_scales(root)
    target_level = pick_pyramid_level(level_scales, args.scaling)
    coarse_level = len(level_scales) - 1
    log(f"Levels available: {level_scales} -- using level {target_level} for decon/seg, "
        f"level {coarse_level} for tissue mask + threshold estimation")

    # --- Coarse-resolution tissue mask + threshold (cheap, whole-slide) ---
    log(f"Reading coarse level {coarse_level} for tissue mask + threshold...")
    coarse_hwc = _to_hwc(np.asarray(root[str(coarse_level)]))
    tissue_mask_coarse = get_tissue_mask(coarse_hwc, subsample=-1, closing=10, fill_holes=25, background_offset=0.05)
    psr_coarse = deconvolve_chunk(coarse_hwc, stain_matrix, stain_index=0)
    threshold = compute_masked_multiotsu_threshold(psr_coarse, tissue_mask_coarse, args.classes, args.class_id)
    log(f"Otsu threshold (from level {coarse_level}): {threshold}")

    # --- Chunk-by-chunk decon + segmentation at the target level ---
    target_arr = root[str(target_level)]
    target_shape = target_arr.shape  # CZYX
    target_hw = target_shape[-2:]

    os.makedirs(args.output_dir, exist_ok=True)
    chunk_hw = (target_arr.chunks[-2], target_arr.chunks[-1])

    # args.input is .../data.zarr/raw -- write psr/mask/collagen as sibling
    # groups in that same data.zarr store rather than separate top-level
    # .zarr directories.
    data_zarr_path = os.path.dirname(args.input.rstrip("/"))
    ensure_zarr_root_group(data_zarr_path)

    psr_out = zarr.create_array(os.path.join(data_zarr_path, "psr"), shape=target_hw,
                                 dtype=np.uint16, chunks=chunk_hw, overwrite=True)
    mask_out = zarr.create_array(os.path.join(data_zarr_path, "mask"), shape=target_hw,
                                  dtype=np.uint8, chunks=chunk_hw, overwrite=True)
    collagen_out = zarr.create_array(os.path.join(data_zarr_path, "collagen"), shape=target_hw,
                                      dtype=np.uint8, chunks=chunk_hw, overwrite=True)

    tiled_res = {"x0": [], "y0": [], "x1": [], "y1": [], "collagen (px^2)": [],
                 "tissue (px^2)": [], "collagen vs tissue (%)": []}

    def _record_and_write(result):
        if result is None:
            return
        region = result["region"]
        y_sl, x_sl = region[-2], region[-1]
        psr_out[y_sl, x_sl] = result["psr_chunk"]
        mask_out[y_sl, x_sl] = result["mask_chunk"]
        collagen_out[y_sl, x_sl] = result["collagen_chunk"]

        collagen_px = int(np.sum(result["collagen_chunk"]))
        tissue_px = int(np.sum(result["mask_chunk"]))
        tiled_res["x0"].append(x_sl.start)
        tiled_res["y0"].append(y_sl.start)
        tiled_res["x1"].append(x_sl.stop)
        tiled_res["y1"].append(y_sl.stop)
        tiled_res["collagen (px^2)"].append(collagen_px)
        tiled_res["tissue (px^2)"].append(tissue_px)
        tiled_res["collagen vs tissue (%)"].append(collagen_px / tissue_px * 100)

    regions = list(iter_chunk_regions(target_shape, target_arr.chunks))
    log(f"{len(regions)} chunks to process at level {target_level} (shape {target_hw})")

    if args.parallel and len(regions) > 1:
        n_workers = args.n_workers or min(multiprocessing.cpu_count(), 8)
        log(f"Processing chunks in parallel with {n_workers} processes...")
        with ProcessPoolExecutor(
            max_workers=n_workers,
            mp_context=multiprocessing.get_context("fork"),
            initializer=_init_decon_seg_worker,
            initargs=(args.input, target_level, tissue_mask_coarse, stain_matrix, threshold, target_hw),
        ) as executor:
            futures = [executor.submit(_decon_seg_one_region, region) for region in regions]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Decon + seg (chunk-wise, parallel)"):
                _record_and_write(future.result())
    else:
        for region in tqdm(regions, desc="Decon + seg (chunk-wise)"):
            rgb_chunk = _to_hwc(np.asarray(target_arr[region]))
            mask_chunk = crop_and_resize_mask_for_region(tissue_mask_coarse, target_hw, region)
            if np.sum(mask_chunk) == 0:
                continue
            psr_chunk = deconvolve_chunk(rgb_chunk, stain_matrix, stain_index=0)
            collagen_chunk = threshold_chunk(psr_chunk, mask_chunk, threshold)
            _record_and_write({
                "region": region,
                "psr_chunk": psr_chunk.astype(np.uint16),
                "mask_chunk": mask_chunk,
                "collagen_chunk": collagen_chunk,
            })

    log("Writing res.csv...")
    pd.DataFrame.from_dict(tiled_res).to_csv(os.path.join(args.output_dir, "res.csv"), index=False)
    log(f"Wrote outputs to {args.output_dir}")


if __name__ == "__main__":
    main(get_args())
