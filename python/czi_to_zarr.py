"""
Stream a CZI whole-slide image into a multiresolution OME-Zarr, tile by tile,
without loading the full stitched image into memory.

Thin CLI wrapper around pyHisto.io.stream_czi_to_ome_zarr. See that function's
docstring for the memory-safety and Windows/SMB sharding rationale.
"""
import argparse
import json

from pyHisto.io import stream_czi_to_ome_zarr
from pyHisto.utils import is_valid_file_or_directory, ensure_zarr_root_group


def get_args():
    parser = argparse.ArgumentParser(prog="czi_to_zarr",
                                      description="Stream a CZI into a multiresolution OME-Zarr")
    parser.add_argument(
        "-i", "--input",
        dest="input",
        help="Path to the input CZI file",
        metavar="PATH",
        type=is_valid_file_or_directory,
        required=True
    )
    parser.add_argument(
        "-o", "--output",
        dest="output",
        help="Path to the output .zarr directory",
        metavar="PATH",
        required=True
    )
    parser.add_argument(
        "--scale-num-levels",
        dest="scale_num_levels",
        help="Number of pyramid levels to generate",
        metavar="INT",
        default=4,
        type=int
    )
    parser.add_argument(
        "--scale-factor",
        dest="scale_factor",
        help="Downsampling factor between consecutive pyramid levels",
        metavar="FLOAT",
        default=2.0,
        type=float
    )
    parser.add_argument(
        "--chunk-size",
        dest="chunk_size",
        help="Chunk size in Y/X (default derived from image size, capped at 1024)",
        metavar="INT",
        default=None,
        type=int
    )
    parser.add_argument(
        "--shard-size",
        dest="shard_size",
        help="Shard size in Y/X, must be a multiple of --chunk-size (default "
             "derived from image size, capped at 4096). Sharding bundles many "
             "chunks into fewer files -- important for reading the store back "
             "over an SMB/Windows share.",
        metavar="INT",
        default=None,
        type=int
    )
    parser.add_argument(
        "--channel-names",
        dest="channel_names",
        help="Comma-separated channel names (e.g. 'R,G,B')",
        metavar="NAMES",
        default=None
    )
    return parser.parse_args()


def main(args):
    # `args.output` is a named child of a shared per-sample zarr store
    # (e.g. <sample>/data.zarr/raw, sibling to psr/mask/collagen written by
    # decon_seg_zarr.py) rather than its own top-level .zarr directory --
    # ensure the shared root group exists first, without disturbing any
    # sibling groups a previous pipeline stage may have already written.
    import os
    ensure_zarr_root_group(os.path.dirname(args.output.rstrip("/")))

    channel_names = args.channel_names.split(",") if args.channel_names else None

    chunk_shape = None
    shard_shape = None
    # n_channels isn't known until the CZI header is read inside
    # stream_czi_to_ome_zarr, so chunk/shard Y-X sizes are passed through as
    # simple ints and expanded there; only override if explicitly requested.
    kwargs = dict(
        scale_num_levels=args.scale_num_levels,
        scale_factor=args.scale_factor,
        channel_names=channel_names,
    )
    if args.chunk_size is not None or args.shard_size is not None:
        # Defer to stream_czi_to_ome_zarr's own n_channels detection by
        # reading the CZI header first via a lightweight probe.
        import aicspylibczi
        import pathlib
        probe = aicspylibczi.CziFile(pathlib.Path(args.input))
        dims_shape = probe.get_dims_shape()[0]
        n_channels = dims_shape['A'][1] if 'A' in dims_shape else (dims_shape['C'][1] if 'C' in dims_shape else 1)

        if args.chunk_size is not None:
            chunk_shape = (n_channels, 1, args.chunk_size, args.chunk_size)
        if args.shard_size is not None:
            shard_shape = (n_channels, 1, args.shard_size, args.shard_size)

    result = stream_czi_to_ome_zarr(
        args.input, args.output,
        chunk_shape=chunk_shape, shard_shape=shard_shape,
        **kwargs
    )

    print(json.dumps({k: (list(v) if isinstance(v, tuple) else str(v)) for k, v in result.items()}, indent=2))


if __name__ == "__main__":
    main(get_args())
