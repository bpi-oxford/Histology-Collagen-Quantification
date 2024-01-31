from aicsimageio.writers.ome_tiff_writer import OmeTiffWriter
from aicsimageio.writers.ome_zarr_writer import OmeZarrWriter
from aicsimageio import AICSImage, types
import aicspylibczi
import pyvips
import pathlib
import histomicstk as htk
from ome_types.model import OME, Image, Pixels, Channel

from tqdm import tqdm
import numpy as np
from skimage.transform import resize
from skimage.filters import threshold_multiotsu
from skimage import exposure
from scipy import ndimage

import multiprocessing
from multiprocessing import Pool
from threading import Lock

import os
import shutil
import argparse

def is_valid_file_or_directory(path):
    """Check if the given path is a valid file or directory."""
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path '{path}' does not exist.")
    return path

def get_args():
    parser = argparse.ArgumentParser(prog="decon",
                            description="WSI color deconvolution tool")
    # Add input path argument
    parser.add_argument(
        "-i", "--input", 
        dest="input",
        help="Path to the input CZI file",
        metavar="PATH",
        type=is_valid_file_or_directory,
        )

    # Add output directory argument
    # Add input path argument
    parser.add_argument(
        "-o", "--output", 
        dest="output",
        help="Path to the output directory",
        metavar="DIR",
        type=is_valid_file_or_directory,
        )

    return parser.parse_args()

def read_tile(args):
    path, m, bbox, x_offset, y_offset = args
    image = aicspylibczi.CziFile(pathlib.Path(path))

    tile = image.read_mosaic((
        image.get_mosaic_tile_bounding_box(M=m).x, 
        image.get_mosaic_tile_bounding_box(M=m).y, 
        image.get_mosaic_tile_bounding_box(M=m).w, 
        image.get_mosaic_tile_bounding_box(M=m).h
    ), C=0)

    x_start =  bbox["x"]-x_offset
    x_end = x_start+bbox["w"]
    y_start = bbox["y"]-y_offset
    y_end = y_start+bbox["h"]
    image_tile = np.transpose(tile[0,:,:,:],(1,0,2)).astype(np.uint16)

    return {
        "x_start":x_start,
        "x_end":x_end,
        "y_start":y_start,
        "y_end":y_end,
        "image_tile":image_tile
        }

def image_read(path):
    image = aicspylibczi.CziFile(pathlib.Path(path))

    image_np = np.zeros((image.get_mosaic_bounding_box().w, image.get_mosaic_bounding_box().h,3), dtype=np.uint16)
    print("image size (px):",image_np.shape)
    tle_bboxes = image.get_all_mosaic_tile_bounding_boxes()

    x_ = [bbox.x for bbox in tle_bboxes.values()]
    y_ = [bbox.y for bbox in tle_bboxes.values()]

    # prepare process regions
    data_to_process = []
    for m, bbox in tqdm(enumerate(tle_bboxes.values()),desc="Preparing tile bounds",total=len(tle_bboxes)):
        data_to_process.append((path, m, {"x":bbox.x, "y":bbox.y, "w":bbox.w, "h":bbox.h}, np.min(x_), np.min(y_)))

    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        results = list(tqdm(pool.imap(read_tile, data_to_process[:]), total=len(tle_bboxes), desc="Reading tiles"))

    for res in tqdm(results,desc="Merging"):
        image_np[res["x_start"]:res["x_end"],res["y_start"]:res["y_end"],:] = res["image_tile"]
        del res

    return image_np

def tiled_deconv_helper(image,roi,W):
    imDeconvolved_batch = htk.preprocessing.color_deconvolution.color_deconvolution(image, W)
    return {"image_tile": imDeconvolved_batch.Stains, "roi":roi}

def stain_vector_separation_large(image, stain_color_map, stains, tile_size=2048, threads=0, batch_size=32):
    print('stain_color_map:', stain_color_map, sep='\n')

    # create stain matrix
    W = np.array([stain_color_map[st] for st in stains]).T

    # perform standard color deconvolution
    imDeconvolved = np.zeros_like(image)

    n_rows, n_cols = image.shape[0:2]

    if threads < 2:
        n_row_batches = (n_rows+batch_size-1)//tile_size
        n_col_batches = (n_cols+batch_size-1)//tile_size

        # create progress bar:
        pbar = tqdm(total=n_row_batches*n_col_batches, desc="Tile deconvolving")

        # this section can be parallelized
        for row_start in range(0,n_rows, tile_size):
            for col_start in range(0,n_cols, tile_size):
                row_end = min(row_start+tile_size, n_rows)
                col_end = min(col_start+tile_size, n_cols)

                # extract a batch from the image tile
                batch = image[row_start:row_end, col_start:col_end, :]

                # tile deconvolution
                imDeconvolved_batch = htk.preprocessing.color_deconvolution.color_deconvolution(batch, W)
                
                # update the output image
                imDeconvolved[row_start:row_end, col_start:col_end] = imDeconvolved_batch.Stains

                pbar.update(1)
        
        pbar.close()
    else:
        region_to_process = []
        for row_start in range(0,n_rows, tile_size):
            for col_start in range(0,n_cols, tile_size):
                row_end = min(row_start+tile_size, n_rows)
                col_end = min(col_start+tile_size, n_cols)
                region_to_process.append((row_start,row_end,col_start,col_end))

        tqdm.write("{} tiles to process".format(len(region_to_process)))

        # run the tiled parallel processing in batch
        if len(region_to_process) % batch_size == 0:
            batch_count = len(region_to_process) // batch_size
        else:
            batch_count = len(region_to_process) // batch_size + 1

        for batch_id in tqdm(range(batch_count), desc="Batch progress"):
            region_to_process_chuck = []

            # batch size for tqdm update only
            if len(region_to_process) < batch_size*(batch_id+1):
                batch_size_ = len(region_to_process)%batch_size
            else:
                batch_size_ = batch_size

            for i in tqdm(range(batch_size_),desc="Loading tiles in batch {}".format(batch_id)):
                tile_idx = batch_id*batch_size + i
                if tile_idx < len(region_to_process):
                    row_start, row_end, col_start, col_end = region_to_process[tile_idx]
                    if isinstance(image, np.ndarray):
                        region_to_process_chuck.append({"tile": image[row_start:row_end,col_start:col_end,:],"roi":(row_start,row_end,col_start,col_end)})
                    else:
                        region_to_process_chuck.append({"tile": image[row_start:row_end,col_start:col_end,:].compute(),"roi":(row_start,row_end,col_start,col_end)})
                else:
                    break

            pbar = tqdm(desc="Tiled color deconvolution in parallel in batch {}/{}".format(batch_id, batch_count),total=batch_size_)
            pbar.clear()

            mutex = Lock()

            def callback_fn(res):
                pbar.update(1)
                row_start,row_end,col_start,col_end = res["roi"]
                img_tile = res["image_tile"]
                with mutex:
                    # imDeconvolved[row_start:row_end,col_start:col_end,:] = da.from_array(img_tile)
                    imDeconvolved[row_start:row_end,col_start:col_end,:] = np.copy(img_tile)

            def callback_err(err):
                print(err)

            # Create a Pool with the specified number of processes
            pool = Pool(threads) # control number of threads to limit memory consumption
            for region in region_to_process_chuck:
                tile = region["tile"]
                roi = region["roi"]
                pool.apply_async(tiled_deconv_helper, (tile,roi,W), callback=callback_fn, error_callback=callback_err)
            pool.close()
            pool.join()
            pbar.close()

    return imDeconvolved

def tiled_resize(image, target_size=None, out_tile_size=2048,anti_aliasing=True, verbose=False):
    # Calculate the new dimensions
    aspect_ratio = image.shape[0] / image.shape[1]
    new_width, new_height = target_size

    # Create a blank image with the new dimensions
    new_image = np.zeros(target_size)

    # Calculate the number of tiles in both dimensions
    num_horizontal_tiles = (new_width + out_tile_size - 1) // out_tile_size
    num_vertical_tiles = (new_height + out_tile_size - 1) // out_tile_size

    # Loop through each tile
    pbar = tqdm(desc="Tiled upsizing", total=num_horizontal_tiles*num_vertical_tiles)
    for y in range(num_vertical_tiles):
        for x in range(num_horizontal_tiles):
            # Calculate the region for the current tile
            left = x * out_tile_size
            lower = y * out_tile_size
            right = min((x + 1) * out_tile_size, new_width)
            upper = min((y + 1) * out_tile_size, new_height)

            # Calculate the corresponding region in the original image
            original_left = int(np.ceil(left / new_width * image.shape[0]))
            original_upper = int(np.ceil(upper / new_height * image.shape[1]))
            original_right = int(np.ceil(right / new_width * image.shape[0]))
            original_lower = int(np.ceil(lower / new_height * image.shape[1]))

            if verbose:
                tqdm.write("original: ({}, {}, {}, {})".format(original_left, original_right, original_lower, original_upper))
                tqdm.write("resampled: ({}, {}, {}, {})".format(left, right, lower, upper))
            exact_resize_shape = (
                right / new_width * image.shape[0]-left / new_width * image.shape[0],
                upper / new_height * image.shape[1]-lower / new_height * image.shape[1],
            )
            error_x = ((original_right-original_left)- exact_resize_shape[0])/exact_resize_shape[0]*100
            error_y = ((original_upper-original_lower)- exact_resize_shape[1])/exact_resize_shape[1]*100
            if verbose:
                tqdm.write("tile resize error x: {:.2f}%".format(error_x))
                tqdm.write("tile resize error y: {:.2f}%".format(error_y) )

            # Crop, resize, and paste the region onto the new image
            region = image[original_left:original_right, original_lower:original_upper]
            
            # TODO: provide option for parallel processing, remind to consider memory consumption
            region = resize(region, (right-left,upper-lower), anti_aliasing=anti_aliasing)

            new_image[left:right, lower:upper] = region
            pbar.update(1)

    return new_image

def psr_background_removal(imDeconvolved, subscaling=100):
    print("Performing background removal on PSR channel...")
    # Tissue Mask
    psr_image = imDeconvolved[:,:,0]
    # Down sample for quick computation
    if not isinstance(psr_image,np.ndarray):
        psr_image_subsampled = psr_image[::subscaling,::subscaling].compute()
    else:
        psr_image_subsampled = psr_image[::subscaling,::subscaling]

    print("Running Otsu multiple thresholding...")
    # otsu thresholding
    thresholds = threshold_multiotsu(psr_image_subsampled,classes=3)

    # Using the threshold values, we generate the three regions.
    regions = np.digitize(psr_image_subsampled, bins=thresholds)

    tissue_mask_subsampled = regions
    tissue_mask_subsampled[tissue_mask_subsampled!=1] = 0

    print("Filling tissue mask...")
    filled_tissue_mask_subsampled = tissue_mask_subsampled
    filled_tissue_mask_subsampled = ndimage.binary_closing(filled_tissue_mask_subsampled, structure=np.ones((25,25))).astype(int)
    filled_tissue_mask_subsampled = ndimage.binary_fill_holes(filled_tissue_mask_subsampled, structure=np.ones((5,5))).astype(int)

    # rescale mask back to original dim
    # tissue_mask = resize(tissue_mask_subsampled.astype(bool), psr_image.shape,anti_aliasing=False)
    print("Upsizing filled tissue mask to full scale...")
    # filled_tissue_mask = resize(filled_tissue_mask_subsampled.astype(bool), psr_image.shape,anti_aliasing=False)
    filled_tissue_mask = tiled_resize(filled_tissue_mask_subsampled.astype(bool), psr_image.shape,anti_aliasing=False)

    # mask the original data
    psr_image_filtered = np.copy(psr_image)
    psr_image_filtered[filled_tissue_mask==0] = 0

    return psr_image_filtered

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

def main(args):
    IMG_PATH = "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR.czi"
    OUTPUT_DIR = "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"
    OUT_TYPE = "TIFF" # TIFF/ZARR

    # read image headers
    image_ = AICSImage(IMG_PATH, reconstruct_mosaic=False)
    pps = types.PhysicalPixelSizes(X=image_.physical_pixel_sizes.X, Y=image_.physical_pixel_sizes.Y, Z=image_.physical_pixel_sizes.Z)

    # read large tiled image
    image_np = image_read(IMG_PATH)

    # color deconvolution
    # human
    stain_color_map = {
        'PSR': [0.376,0.787,0.489],
        'FG': [0.943,0.217,0.254],
        'Residual': [0.123,0.480,-0.868]
    }

    imDeconvolved = stain_vector_separation_large(image_np[::5,::5,:], stain_color_map, stains=stain_color_map.keys(), tile_size=4096,threads=multiprocessing.cpu_count(), batch_size=64)
    
    # background removal
    psr_image_filtered = psr_background_removal(imDeconvolved,subscaling=20)
    
    # save color deconvolved image
    os.makedirs(OUTPUT_DIR,exist_ok=True)

    # TODO: auto channel colors from stain vectors
    channel_colors = ["FFFFFF","FFFFFF","FFFFFF"]
    channel_colors_int = [int(c, 16) for c in channel_colors]

    if OUT_TYPE == "TIFF":
        image_path = os.path.join(OUTPUT_DIR,"color_decon.ome.tiff")
        pyramidal_ome_tiff_write(imDeconvolved, image_path, resX=pps.X, resY=pps.Y,channel_colors=channel_colors_int)

        # output background removed psr channel only
        image_path = os.path.join(OUTPUT_DIR,"PSR.ome.tiff")
        pyramidal_ome_tiff_write(psr_image_filtered[:,:,np.newaxis], image_path, resX=pps.X, resY=pps.Y)
    elif OUT_TYPE == "ZARR":
        image_path = os.path.join(OUTPUT_DIR,"color_decon.zarr")
        if os.path.exists(image_path):
            shutil.rmtree(image_path)

        writer = OmeZarrWriter(image_path)

        writer.write_image(
            imDeconvolved, 
            image_name="color_decon", 
            physical_pixel_sizes=pps,
            channel_names=["PSR","FG","Residual"],
            channel_colors=channel_colors_int,
            scale_num_levels=3,
            scale_factor=2.0,
            dimension_order="CZYX"
            )

if __name__ == "__main__":
    args = get_args()
    main(args)