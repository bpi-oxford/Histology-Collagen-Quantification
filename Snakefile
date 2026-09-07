"""
Collagen quantification pipeline: to_zarr -> decon_seg_zarr -> summary -> ROI export -> QC preview.

Run via pixi (recommended):
    pixi run pipeline --configfile config/dafni_human.yaml

Or directly:
    snakemake --cores 4 --configfile config/dafni_human.yaml

Each sample's ".czi" file in `data_dir` is processed independently into
`<output_dir>/<sample>/`:
    data.zarr/raw                              (to_zarr -- streamed, memory-safe
                                                multires OME-Zarr conversion)
    data.zarr/{psr,mask,collagen}, res.csv     (decon_seg_zarr -- chunk-wise
                                                decon+seg reading directly from
                                                data.zarr/raw; tissue mask + Otsu
                                                threshold from the coarsest
                                                pyramid level, decon/seg run
                                                chunk-by-chunk at `scaling`)
    res_all.csv                                (summary -- whole-slide collagen
                                                /tissue ratio, aggregated from
                                                res.csv)
    collagen_roi.geojson                       (roi -- QuPath/Fiji-loadable ROI,
                                                exported from data.zarr/collagen)
    qc_preview.png                             (qc_preview -- overview + zoom
                                                crops for visual QC)

All of raw/psr/mask/collagen live as named children of ONE zarr store per
sample (data.zarr) rather than four separate top-level .zarr directories --
easier to manage/move/archive as a single unit per sample. Each stage only
ever overwrites its own named child (zarr's shutil.rmtree()/create_array(...,
overwrite=True) is scoped to that child's subdirectory), so re-running one
stage never disturbs siblings already written by another.

decon.py/seg.py (the older CZI-in-memory scripts) are still available for
standalone/manual use but are NOT wired into this pipeline: they build the
full stitched image in memory and were observed to OOM-kill on the smallest
file in this cohort on a 125GB-RAM machine. decon_seg_zarr.py replaces them
here with a chunk-wise, memory-bounded implementation.
"""
import glob
import os

DATA_DIR = config["data_dir"]
OUTPUT_DIR = config["output_dir"]

SAMPLES = [
    os.path.splitext(os.path.basename(f))[0]
    for f in glob.glob(os.path.join(DATA_DIR, "*.czi"))
]

rule all:
    input:
        expand(os.path.join(OUTPUT_DIR, "{sample}", "res_all.csv"), sample=SAMPLES),
        expand(os.path.join(OUTPUT_DIR, "{sample}", "collagen_roi.geojson"), sample=SAMPLES),
        expand(os.path.join(OUTPUT_DIR, "{sample}", "qc_preview.png"), sample=SAMPLES),

rule to_zarr:
    input:
        czi=os.path.join(DATA_DIR, "{sample}.czi"),
    output:
        marker=os.path.join(OUTPUT_DIR, "{sample}", "data.zarr", "raw", ".zattrs_marker"),
    params:
        zarr_path=os.path.join(OUTPUT_DIR, "{sample}", "data.zarr", "raw"),
        scale_num_levels=config.get("zarr_scale_num_levels", 4),
        scale_factor=config.get("zarr_scale_factor", 2.0),
        # Shard size chosen to keep the zarr store's file count low, which
        # matters specifically when reading it back over an SMB/Windows
        # share (per-file open overhead there is much higher than local
        # Linux/Mac storage) -- see stream_czi_to_ome_zarr's docstring.
        shard_size=config.get("zarr_shard_size", 4096),
        chunk_size=config.get("zarr_chunk_size", 1024),
        # Parallel tile reading has an unresolved memory growth issue on
        # real data (see stream_czi_to_ome_zarr's write-loop comments) --
        # default stays parallel (faster) but this can be flipped to
        # sequential via config until it's root-caused.
        no_parallel_flag="--no-parallel" if not config.get("zarr_parallel", True) else "",
    shell:
        """
        python3 python/czi_to_zarr.py \
            -i {input.czi} \
            -o {params.zarr_path} \
            --scale-num-levels {params.scale_num_levels} \
            --scale-factor {params.scale_factor} \
            --chunk-size {params.chunk_size} \
            --shard-size {params.shard_size} \
            {params.no_parallel_flag}
        touch {output.marker}
        """

rule decon_seg_zarr:
    input:
        marker=os.path.join(OUTPUT_DIR, "{sample}", "data.zarr", "raw", ".zattrs_marker"),
    output:
        stat=os.path.join(OUTPUT_DIR, "{sample}", "res.csv"),
        collagen=directory(os.path.join(OUTPUT_DIR, "{sample}", "data.zarr", "collagen")),
    params:
        zarr_path=os.path.join(OUTPUT_DIR, "{sample}", "data.zarr", "raw"),
        out_dir=os.path.join(OUTPUT_DIR, "{sample}"),
        stain_map=config["stain_map"],
        scaling=config["scaling"],
        classes=config["classes"],
        class_id=config["class_id"],
    shell:
        """
        python3 python/decon_seg_zarr.py \
            -i {params.zarr_path} \
            -o {params.out_dir} \
            --stain_map {params.stain_map} \
            -s {params.scaling} \
            --classes {params.classes} \
            -c {params.class_id}
        """

rule summary:
    input:
        stat=os.path.join(OUTPUT_DIR, "{sample}", "res.csv"),
    output:
        summary=os.path.join(OUTPUT_DIR, "{sample}", "res_all.csv"),
    params:
        out_dir=os.path.join(OUTPUT_DIR, "{sample}"),
    shell:
        """
        python3 python/tiled_overlay.py -d {params.out_dir}
        """

rule roi:
    input:
        collagen=os.path.join(OUTPUT_DIR, "{sample}", "data.zarr", "collagen"),
    output:
        geojson=os.path.join(OUTPUT_DIR, "{sample}", "collagen_roi.geojson"),
    params:
        scaling=config["roi_scaling"],
        min_area=config["roi_min_area"],
    shell:
        """
        python3 python/export_roi.py \
            -i {input.collagen} \
            -o {output.geojson} \
            --scaling {params.scaling} \
            --min-area {params.min_area}
        """

rule qc_preview:
    input:
        stat=os.path.join(OUTPUT_DIR, "{sample}", "res.csv"),
        collagen=os.path.join(OUTPUT_DIR, "{sample}", "data.zarr", "collagen"),
    output:
        png=os.path.join(OUTPUT_DIR, "{sample}", "qc_preview.png"),
    params:
        in_dir=os.path.join(OUTPUT_DIR, "{sample}"),
        n_crops=config.get("qc_n_crops", 3),
        czi_path=os.path.join(DATA_DIR, "{sample}.czi"),
    shell:
        """
        python3 python/qc_preview.py \
            -i {params.in_dir} \
            -o {output.png} \
            --n-crops {params.n_crops} \
            --czi-path {params.czi_path}
        """
