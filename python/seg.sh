#!/bin/bash

# List of directories
# directories=(
#     "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR" 
#     "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR" 
#     "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR" 
#     "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"
#     )

# DATA_DIR="/mnt/Data/Jacky/Nan/Blaise- Histology 16 wk Lung Scan 20-08-24/Slide Scanner/240819_Blaise_Nan"
# DATA_DIR="/mnt/Data/Jacky/Nan/nanozoomer"
# DATA_DIR="/mnt/Data/Jacky/Nan/Imaging_MollySK/split_scene"
DATA_DIR="/mnt/Data/Jacky/Nan/250213_1st Bleo Expt/split_scene"
directories=("$DATA_DIR"/*/)    # This creates an array of the full paths to all subdirs

TILE=2048
PADDING=0
CLASS=1

# Loop through the paired data
i=0
# Get the length of the array
length=${#directories[@]}

for directory in "${directories[@]}"
do
    # Check if the directory exists
    if [ -d "$directory" ]; then
        echo "Processing directory ($i/$length): $directory"
        
        input=$directory/PSR.ome.tiff
        output=$directory/collagen.ome.tiff
        mask=$directory/mask.ome.tiff
        stat=$directory/res.csv

        python3 seg.py -i "$input" -o "$output" -s "$stat" -m "$mask" -t "$TILE" -p "$PADDING" -c $CLASS
    else
        echo "Directory not found: $directory"
    fi
    i=$((i+1))
    # exit
done