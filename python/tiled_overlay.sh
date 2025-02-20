#!/bin/bash

directories=(
    "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR"
    "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR"
    "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR"
    "/media/USB_disk/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"
)

length=${#directories[@]}

# Loop through the data
i=0
for d in "${directories[@]}"
do

    # Check if the directory exists
    if [ -e "$d" ]; then
        echo "Processing file ($i/$length): $d"
        
        # image=$directory/collagen.ome.tiff
        # output=$directory/overlay_density.ome.tiff
        # res=$directory/res.csv

        python3 tiled_overlay.py -d "$d"
    else
        echo "Directory not found: $d"
    fi
    i=$((i+1))
done