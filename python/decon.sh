#!/bin/bash

DATA_DIR="/mnt/Data/Jacky/Nan/Blaise- Histology 16 wk Lung Scan 20-08-24/Slide Scanner/240819_Blaise_Nan"


# Associative array for paired data
declare -A paired_io

# Add paired data to the array
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR-Split_Scenes-03.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"
# paired_io["/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR.czi"]="/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"

# Loop through the directory and append each file to the array
for file in "$DATA_DIR"/*; do
    if [[ $file == *.czi ]]; then
        # echo "$file"
        # Get the filename without the suffix
        filename=$(basename "$file")
        filename_no_suffix="${filename%.*}"
        paired_io["$file"]="$DATA_DIR"/$filename_no_suffix
    fi
done

echo "Performing batch colour deconvolution"
SCALING=2

# Loop through the paired data
i=0
# Get the length of the array
length=${#paired_io[@]}

for input in "${!paired_io[@]}"; do
    ouptut=${paired_io[$input]}
    echo  "Processing item $((i+1))/$length: Input File: $input, Output Dir: $ouptut"
    python decon.py -i "$input" -o "$ouptut" -s $SCALING
    i=$((i+1))
done