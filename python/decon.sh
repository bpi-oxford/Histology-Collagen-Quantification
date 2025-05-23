#!/bin/bash

# DATA_DIR="/mnt/Data/Jacky/Nan/Imaging_MollySK/split_scene"
DATA_DIR="/mnt/Data/Jacky/Nan/250213_1st Bleo Expt/split_scene"
DATA_DIR="/mnt/Data/Jacky/Nan/Nan Fast Green PSR Staining/split_scene"
SCALING=2
MANUAL_MASK="false"
STAIN_COLOR_MAP="./stain_color_map/nan_fast_green_psr_staining.json"

# Associative array for paired data
declare -A paired_io

# Add paired data to the array
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR-Split_Scenes-03.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"

# Loop through the directory and append each file to the array
extensions=("ome.tif" "ome.tiff" "czi" "tif" "tiff")


for file in "$DATA_DIR"/*; do
    for ext in "${extensions[@]}"; do
        if [[ "$file" == *.$ext ]]; then
            filename=$(basename "$file")
            filename_no_suffix="$(basename "$filename" .$ext)"
            paired_io["$file"]="$DATA_DIR"/$filename_no_suffix
            break
        fi
    done
done

echo "Performing batch colour deconvolution"


# Loop through the paired data
i=0
# Get the length of the array
length=${#paired_io[@]}

for input in "${!paired_io[@]}"; do
    output=${paired_io[$input]}
    echo  "Processing item $((i+1))/$length: Input File: $input, Output Dir: $output"
    if [ "$MANUAL_MASK" = "true" ]; then
        mask=${paired_io[$input]}.geojson
        python decon.py -i "$input" -o "$output" -s $SCALING -m "$mask" --stain-color-map "$STAIN_COLOR_MAP"
    else
        python decon.py -i "$input" -o "$output" -s $SCALING --stain-color-map "$STAIN_COLOR_MAP"
    fi
    i=$((i+1))
    # break
done