import os
import sys
import shutil
import argparse

# Windows libvips PATH configuration
# Must be imported before pyvips on Windows
if sys.platform == 'win32':
    try:
        import vips_path_windows
    except ImportError:
        print("Warning: vips_path_windows.py not found. Attempting to configure libvips PATH manually...")

        # Fallback: read from config file or use common paths
        from pathlib import Path
        import configparser

        vips_dirs = []

        # Try to read config file
        config_file = Path(__file__).parent.parent / ".vips_config.ini"
        if config_file.exists():
            try:
                config = configparser.ConfigParser()
                config.read(config_file)
                if 'libvips' in config:
                    install_dir = config['libvips'].get('install_dir', '').strip()
                    if install_dir:
                        vips_dirs.append(install_dir)
                    search_paths = config['libvips'].get('search_paths', '').strip()
                    if search_paths:
                        vips_dirs.extend([p.strip() for p in search_paths.split(',')])
            except Exception as e:
                print(f"Warning: Could not read config file: {e}")

        # Add common fallback paths
        vips_dirs.extend([
            r'C:\vips-dev-8.16.0',
            r'D:\vips\vips-dev-8.16.0',
            r'D:\MSVC-build\vips\vips-dev-8.16.0',
        ])

        vips_found = False
        for vips_dir in vips_dirs:
            vips_bin = os.path.join(vips_dir, 'bin')
            if os.path.exists(vips_bin):
                os.environ['PATH'] = vips_bin + ';' + os.environ['PATH']
                print(f"✓ Added libvips to PATH: {vips_bin}")
                vips_found = True
                break

        if not vips_found:
            print("ERROR: libvips not found! Please run: bash setup_windows.sh")
            sys.exit(1)

import vips_path_windows  # Must be imported before pyvips on Windows
import pyvips
import tifffile
from ome_types.model import OME, Image, Pixels, Channel

from skimage.filters import threshold_multiotsu
from skimage import exposure
from tqdm import tqdm
import numpy as np
from skimage.transform import resize
import pandas as pd

import multiprocessing
from multiprocessing import Pool
from threading import Lock

from pyHisto.io import pyramidal_ome_tiff_write
from pyHisto.utils import is_valid_file_or_directory

def _get_physical_pixel_area(path):
    """
    Physical pixel area (X * Y, in the OME-TIFF's declared units, typically um^2)
    read from an OME-TIFF's embedded metadata, as written by
    pyHisto.io.pyramidal_ome_tiff_write's resX/resY. Falls back to 1.0 (i.e.
    raw pixel-count units) if the file has no readable OME physical pixel size.
    """
    try:
        import ome_types
        ome = ome_types.from_tiff(path)
        pixels = ome.images[0].pixels
        size_x = pixels.physical_size_x
        size_y = pixels.physical_size_y
        if not size_x or not size_y:
            raise ValueError("physical_size_x/y not set in OME metadata")
        return float(size_x) * float(size_y)
    except Exception as e:
        print(f"Warning: could not read physical pixel size from '{path}', "
              f"falling back to raw pixel units (pixel_size=1): {e}")
        return 1.0

def iterate_over_regions(image, mask, tile_size, overlap_size):
    assert image.shape==mask.shape, "image and mask shape inconsistent"

    image_height, image_width = image.shape[:2]
    
    # Iterate over rows
    for y in range(0, image_height - tile_size + 1, tile_size - overlap_size):
        # Iterate over columns
        for x in range(0, image_width - tile_size + 1, tile_size - overlap_size):
            # Extract tile
            x_max = min(x+tile_size,image_width)
            y_max = min(y+tile_size,image_height)

            image_tile = image[y:y_max, x:x_max]
            if mask is not None:
                mask_tile = mask[y:y_max, x:x_max]
                yield (x,y, x_max, y_max ,image_tile,mask_tile)
            else:
                yield (x,y, x_max, y_max ,image_tile)


def get_args():
    parser = argparse.ArgumentParser(prog="seg",
                                     description="WSI collagen segmentation from PSR deconvolved channel")
    parser.add_argument(
        "-i", "--input", 
        dest="input",
        help="Path to the input OME TIFF file",
        metavar="PATH",
        type=is_valid_file_or_directory,
        required=True
        )
    parser.add_argument(
        "-m", "--mask", 
        dest="mask",
        help="Path to the tissue mask OME TIFF file",
        metavar="PATH",
        type=is_valid_file_or_directory,
        )
    parser.add_argument(
        "-o", "--output", 
        dest="output",
        help="Path to the output file",
        metavar="PATH",
        required=True
        )
    parser.add_argument(
        "-s", "--stat", 
        dest="stat",
        help="Path to the statistics output file",
        metavar="PATH",
        )
    parser.add_argument(
        "-t", "--tile",
        dest="tile",
        help="Tile size for local measurements",
        metavar="INT",
        default=None
    )
    parser.add_argument(
        "-p", "--padding",
        help="Tile padding for local measurements",
        metavar="INT",
        default=0
    )
    parser.add_argument(
        "-c", "--class",
        dest="class_id",
        help="Selected class ID",
        metavar="INT",
        default=0,
        type=int
    )
    parser.add_argument(
        "--classes",
        dest="classes",
        help="Number of classes for multi-level Otsu thresholding",
        metavar="INT",
        default=4,
        type=int
    )

    return parser.parse_args()

def main(args):
    print("Reading image...")
    image = tifffile.imread(args.input)
    if args.mask:
        print("Reading mask...")
        mask = tifffile.imread(args.mask)

    # # Down sample for quick computation
    # if not isinstance(image,np.ndarray):
    #     image_subsampled = image[::10,::10].compute()
    # else:
    #     image_subsampled = image[::10,::10]

    print("Calculating multiple Otsu values...")
    if args.mask:
        # Extract the pixel values within the masked region
        masked_pixels = image[mask > 0]
    
        # Compute the multi-level Otsu thresholds
        thresholds = threshold_multiotsu(masked_pixels, classes=args.classes)
    else:
        thresholds = threshold_multiotsu(image[::1,::1],classes=args.classes) # full size requires high memory usage, consistency not tested
    threshold = thresholds[args.class_id]
    print("Otsu threshold value: ", threshold)
    
    # Segmentation
    collagen = np.zeros_like(image,dtype=np.uint8)
    collagen[(image>0) & (image<threshold)] = 1

    # output tissue mask
    pyramidal_ome_tiff_write(collagen.T[:,:,np.newaxis], args.output, resX=1.0, resY=1.0)

    # Area Quantification
    if args.stat:
        pixel_size = _get_physical_pixel_area(args.input)

        if args.tile:
            tiled_res = {
                "x0": [],
                "y0": [],
                "x1": [],
                "y1": [],
                "collagen (px^2)": [],
            }
            if args.mask:
                tiled_res["tissue (px^2)"] = []
                tiled_res["collagen vs tissue (%)"] = []
            for x, y, x_max, y_max, image_tile, mask_tile in tqdm(iterate_over_regions(collagen, mask,tile_size=int(args.tile),overlap_size=int(args.padding)),desc="Computing tiled collagen density"):
                if np.sum(mask_tile) == 0:
                    continue

                tiled_res["x0"].append(x)
                tiled_res["y0"].append(y)
                tiled_res["x1"].append(x_max)
                tiled_res["y1"].append(y_max)
                tiled_res["collagen (px^2)"].append(np.sum(image_tile)*pixel_size)
                if args.mask:
                    tiled_res["tissue (px^2)"].append(np.sum(mask_tile))
                    tiled_res["collagen vs tissue (%)"].append(np.sum(image_tile)/np.sum(mask_tile)*100)

            tiled_res = pd.DataFrame.from_dict(tiled_res)

            print("Saving output...")
            tiled_res.to_csv(args.stat,index=False)
        else:
            collagen_area = np.sum(collagen)*pixel_size
            res = {
                "collagen (px^2)": collagen_area,
             }
            if mask is not None:
                tissue_area = np.sum(mask)*pixel_size
                res["tissue (px^2)"] = tissue_area
                res["collagen vs tissue (%)"] = collagen_area/tissue_area*100

            res = pd.Series(res)

            print("Measurement result:")
            print(res)

            print("Saving output...")
            res.to_csv(args.stat,index=False)

if __name__ == "__main__":
    args = get_args()
    main(args)