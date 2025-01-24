import os
import shutil
from tqdm import tqdm

def main():
    DATA_DIR = "/mnt/Ceph/jacky/Klara/PSR/241129 TUNEL Perilipin1 HFD10 gWAT/split_scene"
    OUTPUT_DIR = "/mnt/Ceph/jacky/Klara/PSR/241129 TUNEL Perilipin1 HFD10 gWAT/res"

    data_dir = []

    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
         # Check if the item is a folder
        if not os.path.isdir(item_path): 
            continue  # If it's a folder, skip to the next iteration
        data_dir.append(item)

    os.makedirs(OUTPUT_DIR,exist_ok=True)
    for item in tqdm(data_dir):
        src = os.path.join(DATA_DIR, item, "res.csv")
        tgt = os.path.join(OUTPUT_DIR, "{}.csv".format(item))

        shutil.copyfile(src,tgt)

if __name__=="__main__":
    main()