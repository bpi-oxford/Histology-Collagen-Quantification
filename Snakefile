"""
Collagen quantification pipeline: to_zarr -> decon -> seg -> summary -> ROI export.

Run via pixi (recommended):
    pixi run pipeline --configfile config/dafni_human.yaml

Or directly:
    snakemake --cores 4 --configfile config/dafni_human.yaml

Each sample's ".czi" file in `data_dir` is processed independently into
`<output_dir>/<sample>/`:
    raw.zarr                                            (to_zarr -- streamed,
                                                          memory-safe multires
                                                          OME-Zarr conversion)
    PSR.ome.tiff, mask.ome.tiff, color_decon.ome.tiff   (decon)
    collagen.ome.tiff, res.csv                          (seg, per-tile)
    res_all.csv                                         (whole-slide summary)
    collagen_roi.geojson                                (QuPath/Fiji ROI)

IMPORTANT: `decon`/`seg`/`summary`/`roi` below still read the raw CZI directly
and build the full stitched image in memory (via pyHisto.io.czi_read) --
this has been observed to OOM-kill on the smallest file in the Dafni human
cohort on a 125GB-RAM machine. Do NOT run `rule all` (which only targets
`raw.zarr` for now) with the old decon/seg targets until those rules are
rewritten to read from `raw.zarr` in chunks instead. The `to_zarr` rule
itself IS memory-safe (streams tile-by-tile via write_region()).
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
        # Only the memory-safe zarr conversion is enabled by default.
        # decon/seg/summary/roi targets are commented out below pending
        # their rewrite to read from raw.zarr instead of the raw CZI.
        expand(os.path.join(OUTPUT_DIR, "{sample}", "raw.zarr", ".zattrs_marker"), sample=SAMPLES),
        # expand(os.path.join(OUTPUT_DIR, "{sample}", "res_all.csv"), sample=SAMPLES),
        # expand(os.path.join(OUTPUT_DIR, "{sample}", "collagen_roi.geojson"), sample=SAMPLES),

rule to_zarr:
    input:
        czi=os.path.join(DATA_DIR, "{sample}.czi"),
    output:
        marker=os.path.join(OUTPUT_DIR, "{sample}", "raw.zarr", ".zattrs_marker"),
    params:
        zarr_path=os.path.join(OUTPUT_DIR, "{sample}", "raw.zarr"),
        scale_num_levels=config.get("zarr_scale_num_levels", 4),
        scale_factor=config.get("zarr_scale_factor", 2.0),
        # Shard size chosen to keep the zarr store's file count low, which
        # matters specifically when reading it back over an SMB/Windows
        # share (per-file open overhead there is much higher than local
        # Linux/Mac storage) -- see stream_czi_to_ome_zarr's docstring.
        shard_size=config.get("zarr_shard_size", 4096),
        chunk_size=config.get("zarr_chunk_size", 1024),
    shell:
        """
        python3 python/czi_to_zarr.py \
            -i {input.czi} \
            -o {params.zarr_path} \
            --scale-num-levels {params.scale_num_levels} \
            --scale-factor {params.scale_factor} \
            --chunk-size {params.chunk_size} \
            --shard-size {params.shard_size}
        touch {output.marker}
        """

rule decon:
    input:
        czi=os.path.join(DATA_DIR, "{sample}.czi"),
    output:
        psr=os.path.join(OUTPUT_DIR, "{sample}", "PSR.ome.tiff"),
        mask=os.path.join(OUTPUT_DIR, "{sample}", "mask.ome.tiff"),
        color=os.path.join(OUTPUT_DIR, "{sample}", "color_decon.ome.tiff"),
    params:
        out_dir=os.path.join(OUTPUT_DIR, "{sample}"),
        scaling=config["scaling"],
        batch_num=config["batch_num"],
        stain_map=config["stain_map"],
    shell:
        """
        python3 python/decon.py \
            -i {input.czi} \
            -o {params.out_dir} \
            -s {params.scaling} \
            -bn {params.batch_num} \
            --stain_map {params.stain_map}
        """

rule seg:
    input:
        psr=os.path.join(OUTPUT_DIR, "{sample}", "PSR.ome.tiff"),
        mask=os.path.join(OUTPUT_DIR, "{sample}", "mask.ome.tiff"),
    output:
        collagen=os.path.join(OUTPUT_DIR, "{sample}", "collagen.ome.tiff"),
        stat=os.path.join(OUTPUT_DIR, "{sample}", "res.csv"),
    params:
        tile_size=config["tile_size"],
        padding=config["padding"],
        classes=config["classes"],
        class_id=config["class_id"],
    shell:
        """
        python3 python/seg.py \
            -i {input.psr} \
            -m {input.mask} \
            -o {output.collagen} \
            -s {output.stat} \
            -t {params.tile_size} \
            -p {params.padding} \
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
        collagen=os.path.join(OUTPUT_DIR, "{sample}", "collagen.ome.tiff"),
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
