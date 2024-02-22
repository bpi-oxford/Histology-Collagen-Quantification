#!/bin/bash

SCALING=2
BATCH_NUM=64

weeks=(
    # "SR 6 weeks HFD19-1" 
    "SR 9 weeks hfd18-1" 
    "SR 16 weeks HFD10" 
    "SR 24 weeks HFD15-1" 
    "SR caloric restriction HFD24"
    )

# Loop through each string in the array
for week in "${weeks[@]}"
do
    # Associative array for paired data
    declare -A paired_io

    # Add paired data to the array
    DATA_DIR="/media/USB_disk/Klara/PSR/$week/split_scene"

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
done
echo "Performing batch colour deconvolution"

# Loop through the paired data
i=0 # begin from 0
# Get the length of the array
length=${#paired_io[@]}

for input in "${!paired_io[@]}"; do
    ouptut=${paired_io[$input]}
    echo "#####################################################################################"
    echo  "Processing item $((i+1))/$length: Input File: $input, Output Dir: $ouptut"
    python decon.py -i "$input" -o "$ouptut" -s $SCALING -bn $BATCH_NUM
    i=$((i+1))
done