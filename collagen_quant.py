from aicsimageio import AICSImage
from aicsimageio.writers import OmeTiffWriter

from tqdm import tqdm
import os

import histomicstk as htk

import numpy as np
from skimage.transform import resize
from scipy import ndimage
from skimage.filters import threshold_multiotsu

import multiprocessing
from multiprocessing import Pool
from threading import Lock

import pandas as pd

import dask.array as da

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

            for i in tqdm(range(batch_size),desc="Loading tiles in batch {}".format(batch_id)):
                tile_idx = batch_id*batch_size + i
                if tile_idx < len(region_to_process):
                    row_start, row_end, col_start, col_end = region_to_process[tile_idx]
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

def collagen_quant(IMAGE_PATH, OUTPUT_DIR, stain_color_map, threads=1):
    print("Loading AICSImage header...")
    image = AICSImage(IMAGE_PATH)
    print("Loading image dask data...")
    image_dask = image.get_image_dask_data("XYS")

    # Perform Stain Vector Separation
    # specify stains of input image
    stains = stain_color_map.keys()

    # # Load image 
    # print("Loading image...")
    # image_np = image_dask.compute()

    # Color deconvolution
    print("Performing color deconvolution")
    imDeconvolved = stain_vector_separation_large(image_dask, stain_color_map, stains, tile_size=4096,threads=threads, batch_size=4)

    # save the deconvolved image
    image_basename = IMAGE_PATH.split(os.sep)[-1].split(".")[0]

    print("Saving color deconvolved PSR channel")

    outpath = os.path.join(OUTPUT_DIR,"{}_color_deconv.tif".format(image_basename))
    writer = OmeTiffWriter()
    # only save PSR channel
    writer.save(imDeconvolved.T[0,:,:],outpath,
                    physical_pixel_sizes=image.physical_pixel_sizes,
                    dim_order="YX",
                    )
    
    # Tissue Mask
    psr_image = imDeconvolved[:,:,0]
    # Down sample for quick computation
    if not isinstance(psr_image,np.ndarray):
        psr_image_subsampled = psr_image[::10,::10].compute()

    # otsu thresholding
    thresholds = threshold_multiotsu(psr_image_subsampled,classes=3)

    # Using the threshold values, we generate the three regions.
    regions = np.digitize(psr_image_subsampled, bins=thresholds)

    tissue_mask_subsampled = regions
    tissue_mask_subsampled[tissue_mask_subsampled!=1] = 0

    filled_tissue_mask_subsampled = tissue_mask_subsampled
    filled_tissue_mask_subsampled = ndimage.binary_closing(filled_tissue_mask_subsampled, structure=np.ones((25,25))).astype(int)
    filled_tissue_mask_subsampled = ndimage.binary_fill_holes(filled_tissue_mask_subsampled, structure=np.ones((5,5))).astype(int)

    # rescale mask back to original dim
    tissue_mask = resize(tissue_mask_subsampled.astype(bool), psr_image.shape,anti_aliasing=False)
    filled_tissue_mask = resize(filled_tissue_mask_subsampled.astype(bool), psr_image.shape,anti_aliasing=False)

    # mask the original data
    psr_image_filtered = np.copy(psr_image)
    psr_image_filtered[filled_tissue_mask==0] = 0

    PERCENTILE = 5

    psr_image_filtered_lin = psr_image_filtered.ravel()
    psr_image_filtered_lin = psr_image_filtered_lin[psr_image_filtered_lin != 0]

    percentile = np.percentile(psr_image_filtered_lin,PERCENTILE)
    print("Percentile threshold value: ", percentile)

    collagen = np.zeros_like(psr_image_filtered,dtype=np.uint8)
    collagen[(psr_image_filtered>0) & (psr_image_filtered<percentile)] = 1
    
    ## Area Quantification
    pixel_size = image.physical_pixel_sizes.X*image.physical_pixel_sizes.Y

    collagen_area = np.sum(collagen)*pixel_size
    tissue_area = np.sum(tissue_mask)*pixel_size
    filled_tissue_area = np.sum(filled_tissue_mask)*pixel_size

    res = {
        "collagen (um^2)": collagen_area,
        "tissue (um^2)": tissue_area,
        "filled_tissue (um^2)": filled_tissue_area,
        "collagen vs tissue (%)": collagen_area/tissue_area*100,
        "collagen vs filled tissue (%)": collagen_area/filled_tissue_area*100,
        }

    res = pd.Series(res)

    print("Measurement result:")
    print(res)

    print("Saving output...")
    res.to_csv(os.path.join(OUTPUT_DIR,"res.csv"))

    ## Save Result
    # save the deconvolved image
    image_basename = IMAGE_PATH.split(os.sep)[-1].split(".")[0]

    outpath = os.path.join(OUTPUT_DIR,"{}_label_collagen.tif".format(image_basename))
    writer = OmeTiffWriter()
    # only save PSR channel
    collagen_ = collagen*255
    writer.save(collagen_.astype(np.uint8).T,outpath,
                physical_pixel_sizes=image.physical_pixel_sizes,
                dim_order="YX",
                )

    outpath = os.path.join(OUTPUT_DIR,"{}_label_tissue.tif".format(image_basename))
    writer = OmeTiffWriter()
    # only save PSR channel
    tissue_mask_ = tissue_mask*255
    writer.save(tissue_mask_.astype(np.uint8).T,outpath,
                physical_pixel_sizes=image.physical_pixel_sizes,
                dim_order="YX",
    )

    outpath = os.path.join(OUTPUT_DIR,"{}_label_filled_tissue.tif".format(image_basename))
    writer = OmeTiffWriter()
    # only save PSR channel
    filled_tissue_mask_ = filled_tissue_mask*255
    writer.save(filled_tissue_mask_.astype(np.uint8).T,outpath,
                physical_pixel_sizes=image.physical_pixel_sizes,
                dim_order="YX",
    )

def main():
    DATA_DIR = "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Mouse"
    # DATA_DIR = "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human"

    stain_color_map = {
        'PSR': [0.496,0.712,0.497],
        'FG': [0.802,0.201,0.562],
        'Residual': [-0.525,-0.21,0.825]
    }
    background = [207,209,206]

    suffices = [
        # ("Mouse_female2-013_w16/s1/Mouse-week16-Fem2-013-PSR_s1.czi","/Mouse_female2-013_w16/s1"),
        # ("Mouse_female2-013_w16/s2/Mouse-week16-Fem2-013-PSR_s2.czi","/Mouse_female2-013_w16/s2"),
        # ("Mouse_female2-013_w16/s4/Mouse-week16-Fem2-013-PSR_s4.czi","/Mouse_female2-013_w16/s4"),
        # ("Mouse_male1_w16/s1/Mouse-week16-male1-028-PSR_s1.czi","Mouse_male1_w16/s1"),
        # ("Mouse_male1_w16/s2/Mouse-week16-male1-028-PSR_s2.czi","Mouse_male1_w16/s2"),
        # ("Mouse_male2_w16/s1/Mouse-week16-Male2-013-PSR_s1.czi","Mouse_male2_w16/s1"),
        # ("Mouse_male2_w16/s2/Mouse-week16-Male2-013-PSR_s2.czi","Mouse_male2_w16/s2"),
        # ("Mouse_male2_w16/s3/Mouse-week16-Male2-013-PSR_s3.czi","Mouse_male2_w16/s3"),
        # ("Mouse_male3_w16/s1/Mouse-week16-Male3-013-lung-PSR_s1.czi","Mouse_male3_w16/s1"),
        # ("Mouse_male3_w16/s2/Mouse-week16-Male3-013-lung-PSR_s2.czi","Mouse_male3_w16/s2"),
        ("Mouse_male3_w16/s3/Mouse-week16-Male3-013-lung-PSR_s3.czi","Mouse_male3_w16/s3_2"),
        # ("21P00124-A4-001-A4-M-less-PSR.czi","21P00124-A4-001-A4-M-less-PSR"),
        # ("21P00124-B8-002-M-adv-PSR.czi ","21P00124-B8-002-M-adv-PSR"),
        # ("21P014858-E5-006-normal-PSR.czi ","21P014858-E5-006-normal-PSR"),
    ]

    for s in suffices:
        IMAGE_PATH = os.path.join(DATA_DIR,s[0])
        OUTPUT_DIR = os.path.join(DATA_DIR,s[1])

        os.makedirs(OUTPUT_DIR,exist_ok=True)
        print("Processing image: ",IMAGE_PATH)
        collagen_quant(IMAGE_PATH,OUTPUT_DIR, stain_color_map, threads=multiprocessing.cpu_count())

if __name__ == "__main__":
    main()