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
    thresholds = threshold_multiotsu(image[::1,::1],classes=4) # full size requires high memory usage, consistency not tested
    threshold = thresholds[1]
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

        collagen_area = np.sum(collagen)*pixel_size
        if mask is not None:
            tissue_area = np.sum(mask)*pixel_size
        res = {
            "collagen (um^2)": collagen_area,
            "tissue (um^2)": tissue_area,
            "collagen vs tissue (%)": collagen_area/tissue_area*100,
            }

        res = pd.Series(res)

        print("Measurement result:")
        print(res)

        print("Saving output...")
        res.to_csv(args.stat)

if __name__ == "__main__":
    args = get_args()
    main(args)