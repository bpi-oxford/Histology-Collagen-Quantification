#!/bin/bash

# List of directories
# directories=(
#     # "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR" 
#     # "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR" 
#     # "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR" 
#     # "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"
#     )

TILE=2048
PADDING=0

DATA_DIR="/media/USB_disk/Klara/PSR/SR 6 weeks HFD19-1/split_scene"
# DATA_DIR="/media/USB_disk/Klara/PSR/SR 9 weeks hfd18-1/split_scene"
# DATA_DIR="/media/USB_disk/Klara/PSR/SR 16 weeks HFD10/split_scene"
# DATA_DIR="/media/USB_disk/Klara/PSR/SR 24 weeks HFD15-1/split_scene"
# DATA_DIR="/media/USB_disk/Klara/PSR/SR caloric restriction HFD24/split_scene"

# mapfile -t directories < <(find "$DATA_DIR" -type d -print0)
directories=("$DATA_DIR"/*/)    # This creates an array of the full paths to all subdirs
DATA_DIR=("${DATA_DIR[@]%/}")            # This removes the trailing slash on each item
DATA_DIR=("${DATA_DIR[@]##*/}")          # This removes the path prefix, leaving just the dir names

# Loop through the paired data
i=0
# Get the length of the array
length=${#directories[@]}

# Iterate through the directories
for directory in "${directories[@]}"
do
    # Check if the directory exists
    if [ -d "$directory" ]; then
        echo "Processing directory ($i/$length): $directory"
        
        input=$directory/PSR.ome.tiff
        output=$directory/collagen.ome.tiff
        mask=$directory/mask.ome.tiff
        stat=$directory/res.csv

        python3 seg.py -i "$input" -o "$output" -s "$stat" -m "$mask" -t "$TILE" -p "$PADDING"
    else
        echo "Directory not found: $directory"
    fi
    i=$((i+1))
    # exit
done