import os
import shutil
from tqdm import tqdm

def main():
    # week = "241109 Aflux young-mid-old PSR gWAT"
    week = "241124 Aflux 6wks PSR gWAT"

    DATA_DIR = "/mnt/Ceph/jacky/Klara/PSR/{}/split_scene".format(week)
    OUTPUT_DIR = "/mnt/Ceph/jacky/Klara/PSR/{}/res".format(week)

    data_dir = []

    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
         # Check if the item is a folder
        if not os.path.isdir(item_path): 
            continue  # If it's a folder, skip to the next iteration
        data_dir.append(item)

    os.makedirs(os.path.join(OUTPUT_DIR,"raw"),exist_ok=True)
    for item in tqdm(data_dir,desc="Copying RAW"):
        src = os.path.join(DATA_DIR, item, "res.csv")
        tgt = os.path.join(OUTPUT_DIR,"raw", "{}.csv".format(item))

        shutil.copyfile(src,tgt)

    os.makedirs(os.path.join(OUTPUT_DIR,"all"),exist_ok=True)
    for item in tqdm(data_dir,desc="Copying all"):
        src = os.path.join(DATA_DIR, item, "res_all.csv")
        tgt = os.path.join(OUTPUT_DIR,"all", "{}.csv".format(item))

        try:
            shutil.copyfile(src,tgt)
        except:
            pass

if __name__=="__main__":
    main()