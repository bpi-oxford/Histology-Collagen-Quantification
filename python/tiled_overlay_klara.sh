#!/bin/bash

weeks=(
    # "SR 6 weeks HFD19-1" 
    # "SR 9 weeks hfd18-1" 
    # "SR 16 weeks HFD10" 
    # "SR 24 weeks HFD15-1" 
    # "SR caloric restriction HFD24" 
    # "subcutaneous"
    "241109 Aflux young-mid-old PSR gWAT"
    "241124 Aflux 6wks PSR gWAT"
    )

for week in "${weeks[@]}"
do
    # DATA_DIR="/media/usb-drive/Klara/PSR/$week"
    # DATA_DIR="/media/USB_disk/Klara/PSR/$week/split_scene"
    DATA_DIR="/mnt/Ceph/jacky/Klara/PSR/$week/split_scene"

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
            
            # image=$directory/collagen.ome.tiff
            # output=$directory/overlay_density.ome.tiff
            # res=$directory/res.csv

            python3 tiled_overlay.py -d "$directory"
        else
            echo "Directory not found: $directory"
        fi
        i=$((i+1))
    done
done