from aicsimageio import AICSImage
from aicsimageio.writers import OmeTiffWriter

import aicspylibczi
import pathlib

import czifile

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

def collagen_quant(IMAGE_PATH, OUTPUT_DIR, stain_color_map, threads=1, subsample=10, threshold=None, threshold_method="manual", preload_image=False, reconstruct_mosaic=True, reader="aicsimageio"):
    # Perform Stain Vector Separation
    # specify stains of input image
    stains = stain_color_map.keys()
    
    if reader == "aicsimageio":
        print("Loading AICSImage header...")
        image = AICSImage(IMAGE_PATH, reconstruct_mosaic=reconstruct_mosaic)

        if reconstruct_mosaic == False:
            print(image.dims)
            print(image.shape)
            print(image.mosaic_tile_dims)
            print(image.get_image_dask_data("XYS",M=1).shape)
            print(image.get_mosaic_tile_positions())
            exit()
        else:
            print("Loading image dask data...")
            image_dask = image.get_image_dask_data("XYS")

        # Load image 
        if preload_image:
            print("Loading image...")
            image_np = image_dask.compute()

            # Color deconvolution
            print("Performing color deconvolution")
            imDeconvolved = stain_vector_separation_large(image_np, stain_color_map, stains, tile_size=4096,threads=threads, batch_size=64)
        else:
            # Color deconvolution
            print("Performing color deconvolution")
            imDeconvolved = stain_vector_separation_large(image_dask, stain_color_map, stains, tile_size=4096,threads=threads, batch_size=64)
    elif reader == "aicspylibczi":
        print("Loading image...")
        mosaic_file = pathlib.Path(IMAGE_PATH)
        image_ = aicspylibczi.CziFile(mosaic_file)
        image = AICSImage(IMAGE_PATH, reconstruct_mosaic=reconstruct_mosaic) # temp workaround for pixel size thing
        # print(image.get_mosaic_scene_bounding_box().x, image.get_mosaic_scene_bounding_box().y, image.get_mosaic_scene_bounding_box().w, image.get_mosaic_scene_bounding_box().h)
        
        if reconstruct_mosaic:
            # Mosaic files ignore the S dimension and use an internal mIndex to reconstruct, the scale factor allows one to generate a manageable image
            image_np = image_.read_mosaic(C=0, scale_factor=1)
            # Color deconvolution
            print("Performing color deconvolution")
            imDeconvolved = stain_vector_separation_large(image_np[0,:,:,:], stain_color_map, stains, tile_size=4096,threads=threads, batch_size=64)
        else:
            # manually read the tiled data
            # print(image_.dims)
            # print(image_.get_dims_shape())
            # print((image_.get_mosaic_scene_bounding_box().h, image_.get_mosaic_scene_bounding_box().w,3,))
            image_np = np.zeros((image_.get_mosaic_bounding_box().w, image_.get_mosaic_bounding_box().h,3), dtype=np.uint16)
            image_np[0:10,0:5, :] = 1
            tle_bboxes = image_.get_all_mosaic_tile_bounding_boxes()
            for m, bbox in tqdm(enumerate(tle_bboxes.values()),desc="Reading tiles",total=len(tle_bboxes)):
                # print("tile:", m)

                # masaic reading fail for 21P00124-B8-002-M-adv-PSR/21P00124-B8-002-M-adv-PSR-Create Image Subset-05.czi, temporary work around
                try:
                    tile = image_.read_mosaic((
                        image_.get_mosaic_tile_bounding_box(M=m).x, 
                        image_.get_mosaic_tile_bounding_box(M=m).y, 
                        image_.get_mosaic_tile_bounding_box(M=m).w, 
                        image_.get_mosaic_tile_bounding_box(M=m).h
                    ), C=0)
                except:
                    continue
                # print("mosaic tile:", image_.get_mosaic_tile_bounding_box(M=m).x, image_.get_mosaic_tile_bounding_box(M=m).y, image_.get_mosaic_tile_bounding_box(M=m).w, image_.get_mosaic_tile_bounding_box(M=m).h)
                # print(tile.shape)
                x_start =  bbox.x
                x_end = bbox.x+bbox.w
                y_start = bbox.y
                y_end = bbox.y+bbox.h
                # print("bounds: ",x_start, x_end, y_start, y_end)
                try:
                    image_np[x_start:x_end, y_start:y_end, :] = np.transpose(tile[0,:,:,:],(1,0,2)).astype(np.uint16)
                except Exception as error:
                    """ 
                    error to handle:
                    Processing image:  /media/jackyko/FOR NAN/01_08_23 PSR and H&E/Human/PSR_cropped/21P00124-B8-002-M-adv-PSR/21P00124-B8-002-M-adv-PSR-Create Image Subset-05.czi
                    Loading image...
                    Reading tiles:   3%|██                                                                                | 1/39 [00:00<00:02, 17.49it/s]
                    Traceback (most recent call last):
                    File "/home/jackyko/Projects/lung_histology/collagen_quant.py", line 401, in <module>
                        main()
                    File "/home/jackyko/Projects/lung_histology/collagen_quant.py", line 398, in main
                        collagen_quant(IMAGE_PATH,OUTPUT_DIR, stain_color_map, threads=multiprocessing.cpu_count(), subsample=10,threshold=60, threshold_method="manual", preload_image=True, reader="aicspylibczi", reconstruct_mosaic=False)
                    File "/home/jackyko/Projects/lung_histology/collagen_quant.py", line 204, in collagen_quant
                        image_np[x_start:x_end, y_start:y_end, :] = np.transpose(tile[0,:,:,:],(1,0,2)).astype(np.uint16)
                    ValueError: could not broadcast input array from shape (2056,741,3) into shape (2056,743,3)
                    """ 
                    print("Error case:", IMAGE_PATH)
                    print("Tile:", m)
                    print(error)
                    continue

                # if m > 50:
                #     break

            # Color deconvolution
            print("Performing color deconvolution")
            imDeconvolved = stain_vector_separation_large(image_np, stain_color_map, stains, tile_size=4096,threads=threads, batch_size=64)

            # # save the deconvolved image
            # image_basename = IMAGE_PATH.split(os.sep)[-1].split(".")[0]
            # outpath = os.path.join(OUTPUT_DIR,"{}_test.tif".format(image_basename))
            # writer = OmeTiffWriter()
            # # only save PSR channel
            # writer.save(image_np[::10,::10,:].astype(np.uint16).T,outpath,
            #             physical_pixel_sizes=image.physical_pixel_sizes,
            #             dim_order="CYX",
            # )
            # exit()

    elif reader == "czifile":
        print("Loading image...")
        image = czifile.imread(IMAGE_PATH)

        imDeconvolved = stain_vector_separation_large(image, stain_color_map, stains, tile_size=4096,threads=threads, batch_size=64)

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
    
    print("Save color deconvolved PSR channel complete")
    
    # Tissue Mask
    psr_image = imDeconvolved[:,:,0]
    # Down sample for quick computation
    if not isinstance(psr_image,np.ndarray):
        psr_image_subsampled = psr_image[::subsample,::subsample].compute()
    else:
        psr_image_subsampled = psr_image[::subsample,::subsample]

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

    if threshold_method == "percentile":
        PERCENTILE = 10

        psr_image_filtered_lin = psr_image_filtered.ravel()
        psr_image_filtered_lin = psr_image_filtered_lin[psr_image_filtered_lin != 0]

        threshold = np.percentile(psr_image_filtered_lin,PERCENTILE)
        print("Percentile threshold value: ", threshold)
    elif threshold_method == "manual":
        if threshold is None:
            raise ValueError("Manual threshold need to provide a value, None is given")
    elif threshold_method == "multiotsu":
        print("Calculating multiple Otsu values...")
        thresholds = threshold_multiotsu(psr_image_filtered,classes=3)
        threshold = thresholds[0]
        print("Otsu threshold value: ", threshold)

    collagen = np.zeros_like(psr_image_filtered,dtype=np.uint8)
    collagen[(psr_image_filtered>0) & (psr_image_filtered<threshold)] = 1
    
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
    # DATA_DIR = "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Mouse"
    # DATA_DIR = "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human"
    DATA_DIR = "/media/jackyko/FOR NAN/01_08_23 PSR and H&E/Human/PSR_cropped"

    # mouse
    # stain_color_map = {
    #     'PSR': [0.496,0.712,0.497],
    #     'FG': [0.802,0.201,0.562],
    #     'Residual': [-0.525,-0.21,0.825]
    # }
    # background = [207,209,206]

    # human
    stain_color_map = {
        'PSR': [0.376,0.787,0.489],
        'FG': [0.943,0.217,0.254],
        'Residual': [0.123,0.480,-0.868]
    }
    background = [207,209,206]

    # suffices = [
        # ("Mouse_female2-013_w16/s1/Mouse-week16-Fem2-013-PSR_s1.czi","Mouse_female2-013_w16/s1"),
        # ("Mouse_female2-013_w16/s2/Mouse-week16-Fem2-013-PSR_s2.czi","Mouse_female2-013_w16/s2"),
        # ("Mouse_female2-013_w16/s4/Mouse-week16-Fem2-013-PSR_s4.czi","Mouse_female2-013_w16/s4"),
        # ("Mouse_male1_w16/s1/Mouse-week16-male1-028-PSR_s1.czi","Mouse_male1_w16/s1"),
        # ("Mouse_male1_w16/s2/Mouse-week16-male1-028-PSR_s2.czi","Mouse_male1_w16/s2"),
        # ("Mouse_male2_w16/s1/Mouse-week16-Male2-013-PSR_s1.czi","Mouse_male2_w16/s1"),
        # ("Mouse_male2_w16/s2/Mouse-week16-Male2-013-PSR_s2.czi","Mouse_male2_w16/s2"),
        # ("Mouse_male2_w16/s3/Mouse-week16-Male2-013-PSR_s3.czi","Mouse_male2_w16/s3"),
        # ("Mouse_male3_w16/s1/Mouse-week16-Male3-013-lung-PSR_s1.czi","Mouse_male3_w16/s1_2"),
        # ("Mouse_male3_w16/s2/Mouse-week16-Male3-013-lung-PSR_s2.czi","Mouse_male3_w16/s2"),
        # ("Mouse_male3_w16/s3/Mouse-week16-Male3-013-lung-PSR_s3.czi","Mouse_male3_w16/s3_2"),
        # ("21P00124-A4-001-A4-M-less-PSR/21P00124-A4-001-A4-M-less-PSR.czi","21P00124-A4-001-A4-M-less-PSR"),
        # ("21P00124-B8-002-M-adv-PSR/21P00124-B8-002-M-adv-PSR.czi","21P00124-B8-002-M-adv-PSR"),
        # ("21P014858-E5-006-normal-PSR/21P014858-E5-006-normal-PSR.czi","21P014858-E5-006-normal-PSR"),
    # ]

    suffices = [
        # ("test/21P00124-B8-002-M-adv-PSR-Create Image Subset-01-Create Image Subset-01.czi","test")
    ]

    for case in os.listdir(DATA_DIR):
        if "adv" not in case:
            continue
        for file in os.listdir(os.path.join(DATA_DIR,case)):
            if file.split(".")[-1] == "czi":
                suffices.append((os.path.join(case,file),os.path.join(case,file.split(".")[0])))

    # can be safer to run in batches
    for s in suffices[0:3]:
        IMAGE_PATH = os.path.join(DATA_DIR,s[0])
        OUTPUT_DIR = os.path.join(DATA_DIR,s[1])

        os.makedirs(OUTPUT_DIR,exist_ok=True)
        print("Processing image: ",IMAGE_PATH)
        collagen_quant(IMAGE_PATH,OUTPUT_DIR, stain_color_map, threads=multiprocessing.cpu_count(), subsample=10,threshold=60, threshold_method="multiotsu", preload_image=True, reader="aicspylibczi", reconstruct_mosaic=False)

if __name__ == "__main__":
    main()