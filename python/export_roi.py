"""
Export a binary collagen segmentation mask as a QuPath/Fiji-loadable GeoJSON
ROI file.

Thin CLI wrapper around pyHisto.utils.mask_to_geojson. Accepts either a
tifffile-readable mask (e.g. collagen.ome.tiff) or a plain Zarr array
directory (e.g. collagen.zarr, as written by decon_seg_zarr.py).
"""
import argparse
import os

import numpy as np

from pyHisto.utils import is_valid_file_or_directory, mask_to_geojson, log


def get_args():
    parser = argparse.ArgumentParser(prog="export_roi",
                                      description="Export a segmentation mask as a GeoJSON ROI file")
    parser.add_argument(
        "-i", "--input",
        dest="input",
        help="Path to the input mask (OME TIFF file or a zarr array, e.g. <sample>/data.zarr/collagen)",
        metavar="PATH",
        type=is_valid_file_or_directory,
        required=True
    )
    parser.add_argument(
        "-o", "--output",
        dest="output",
        help="Path to the output GeoJSON file",
        metavar="PATH",
        required=True
    )
    parser.add_argument(
        "--scaling",
        dest="scaling",
        help="Scale factor applied to polygon coordinates (e.g. to map a mask "
             "computed on a downsampled image back to full-resolution coordinates)",
        metavar="FLOAT",
        default=1.0,
        type=float
    )
    parser.add_argument(
        "--min-area",
        dest="min_area",
        help="Discard polygons with area (in scaled coordinate units) below this threshold",
        metavar="FLOAT",
        default=0.0,
        type=float
    )
    return parser.parse_args()


def _read_mask(path):
    # A zarr array directory has a zarr.json (v3) or .zarray (v2) marker at
    # its root -- check for that rather than a ".zarr" path suffix, since a
    # named child of a shared store (e.g. data.zarr/collagen) won't have one.
    if os.path.isdir(path) and (
        os.path.exists(os.path.join(path, "zarr.json")) or os.path.exists(os.path.join(path, ".zarray"))
    ):
        import zarr
        return np.asarray(zarr.open_array(path, mode="r"))
    import tifffile
    return tifffile.imread(path)


def main(args):
    log(f"Reading mask from {args.input}...")
    mask = _read_mask(args.input)

    log("Extracting ROI polygons...")
    gdf = mask_to_geojson(mask, out_path=args.output, scaling_factor=args.scaling, min_area=args.min_area)

    log(f"Wrote {len(gdf)} ROI(s) to {args.output}")


if __name__ == "__main__":
    main(get_args())
