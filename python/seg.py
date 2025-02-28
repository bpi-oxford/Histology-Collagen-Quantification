import os
import shutil
import argparse

from aicsimageio.writers.ome_tiff_writer import OmeTiffWriter
from aicsimageio.writers.ome_zarr_writer import OmeZarrWriter
from aicsimageio import AICSImage, types
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

def pyramidal_ome_tiff_write(image, path, resX=1.0, resY=1.0, units="µm", tile_size=2048, channel_colors=None):
    """
    Pyramidal ome tiff write is only support in 2D + C data.
    Input dimension order has to be XYC
    """

    assert len(image.shape) == 3, "Input dimension order must be XYC, get array dimension of {}".format(len(image.shape)) 

    size_x, size_y, size_c = image.shape
    
    if image.dtype == np.uint8:
        format = "uchar"
        data_type = "uint8"
    elif image.dtype == np.uint16:
        format = "ushort"
        data_type = "uint16"
    else:
        raise TypeError(f"Expected an uint8 or uint16 image, but received {image.dtype}")

    im_vips = pyvips.Image.new_from_memory(image.transpose(1,0,2).reshape(-1,size_c).tobytes(), size_x, size_y, bands=size_c, format=format) 
    im_vips = pyvips.Image.arrayjoin(im_vips.bandsplit(), across=1) # for multichannel write
    im_vips.set_type(pyvips.GValue.gint_type, "page-height", size_y)

    # build minimal OME metadata
    ome = OME()

    if channel_colors is None:
        channel_colors = [-1 for _ in range(size_c)]

    img = Image(
        id="Image:0",
        name="resolution_1",
        pixels=Pixels(
            id="Pixels:0", type=data_type, dimension_order="XYZTC",
            size_c=size_c, size_x=size_x, size_y=size_y, size_z=1, size_t=1, 
            big_endian=False, metadata_only=True,
            physical_size_x=resX,
            physical_size_x_unit=units,
            physical_size_y=resY,
            physical_size_y_unit=units,
            channels= [Channel(id=f"Channel:0:{i}", name=f"Ch_{i}", color=channel_colors[i]) for i in range(size_c)]
        )
    )

    ome.images.append(img)

    def eval_cb(image, progress):
        pbar_filesave.update(progress.percent - pbar_filesave.n)

    im_vips.set_progress(True)

    pbar_filesave = tqdm(total=100, unit="Percent", desc="Writing pyramidal OME TIFF", position=0, leave=True)
    im_vips.signal_connect('eval', eval_cb)
    im_vips.set_type(pyvips.GValue.gstr_type, "image-description", ome.to_xml())

    im_vips.write_to_file(
        path, 
        compression="lzw",
        tile=True, 
        tile_width=tile_size,
        tile_height=tile_size,
        pyramid=True,
        depth="onetile",
        subifd=True,
        bigtiff=True
        )

def is_valid_file_or_directory(path):
    """Check if the given path is a valid file or directory."""
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path '{path}' does not exist.")
    return path

def get_args():
    parser = argparse.ArgumentParser(prog="decon",
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
        thresholds = threshold_multiotsu(masked_pixels, classes=4)
    else:
        thresholds = threshold_multiotsu(image[::1,::1],classes=4) # full size requires high memory usage, consistency not tested
    threshold = thresholds[args.class_id]
    print("Otsu threshold value: ", threshold)
    
    # Segmentation
    collagen = np.zeros_like(image,dtype=np.uint8)
    collagen[(image>0) & (image<threshold)] = 1

    # output tissue mask
    pyramidal_ome_tiff_write(collagen.T[:,:,np.newaxis], args.output, resX=1.0, resY=1.0)

    # Area Quantification
    if args.stat:
        # pixel_size = image.physical_pixel_sizes.X*image.physical_pixel_sizes.Y
        pixel_size = 1*1

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
                tiled_res
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
                res["tissue (px^2)"] = tissue_area,
                res["collagen vs tissue (%)"] = collagen_area/tissue_area*100,
                tissue_area = np.sum(mask)*pixel_size

            res = pd.Series(res)

            print("Measurement result:")
            print(res)

            print("Saving output...")
            res.to_csv(args.stat,index=False)

if __name__ == "__main__":
    args = get_args()
    main(args)