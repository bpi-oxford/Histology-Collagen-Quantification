"""
Export a binary collagen segmentation mask as a QuPath/Fiji-loadable GeoJSON
ROI file.

Thin CLI wrapper around pyHisto.utils.mask_to_geojson.
"""
import argparse

import tifffile

from pyHisto.utils import is_valid_file_or_directory, mask_to_geojson


def get_args():
    parser = argparse.ArgumentParser(prog="export_roi",
                                      description="Export a segmentation mask as a GeoJSON ROI file")
    parser.add_argument(
        "-i", "--input",
        dest="input",
        help="Path to the input mask OME TIFF file (e.g. collagen.ome.tiff)",
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


def main(args):
    print(f"Reading mask from {args.input}...")
    mask = tifffile.imread(args.input)

    print("Extracting ROI polygons...")
    gdf = mask_to_geojson(mask, out_path=args.output, scaling_factor=args.scaling, min_area=args.min_area)

    print(f"Wrote {len(gdf)} ROI(s) to {args.output}")


if __name__ == "__main__":
    main(get_args())
