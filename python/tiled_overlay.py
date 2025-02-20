import tifffile
import pyvips
from ome_types.model import OME, Image, Pixels, Channel
import pandas as pd
import numpy as np

import argparse
import os

from pyHisto import io, utils

def tile_overlay():
    return

def is_valid_file_or_directory(path):
    """Check if the given path is a valid file or directory."""
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path '{path}' does not exist.")
    return path

def get_args():
    parser = argparse.ArgumentParser(prog="decon",
                                     description="WSI collagen segmentation post processing script")
    parser.add_argument(
        "-d",
        dest="dir",
        help="Working directory",
        required=True,
        type=is_valid_file_or_directory
    )
    # parser.add_argument(
    #     "-i", "--input", 
    #     dest="input",
    #     help="Path to the input OME TIFF file",
    #     metavar="PATH",
    #     type=is_valid_file_or_directory,
    #     required=True
    #     )
    # parser.add_argument(
    #     "-o", "--output", 
    #     dest="output",
    #     help="Path to the output file",
    #     metavar="PATH",
    #     required=True
    #     )
    # parser.add_argument(
    #     "-r", "--res", 
    #     dest="res",
    #     help="Result file contains overlay data",
    #     metavar="PATH",
    #     )

    return parser.parse_args()

def main(args):
    print("Reading image...")
    OUT_FILE = os.path.join(args.dir,"res_all.csv")
    
    collagen = tifffile.imread(os.path.join(args.dir,"collagen.ome.tiff"))
    res = pd.read_csv(os.path.join(args.dir,"res.csv"))

    res_all = res[["collagen (px^2)","tissue (px^2)"]].sum()
    res_all["collagen vs tissue (%)"] = res_all["collagen (px^2)"]/res_all["tissue (px^2)"]*100
    print(res_all)

    res_all.to_csv(OUT_FILE,index=True)

if __name__ == "__main__":
    args = get_args()
    main(args)