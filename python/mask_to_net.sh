#!/bin/bash

# List of directories
directories=(
    "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A4-002-M-less-PSR" 
    "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00561-A5-002-M-adv-PSR" 
    "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A2-002-M-less_PSR" 
    "/media/Data3/Jacky/Data/Dafni_lung_slide_scans/Human/21P00655-A7-025-M-Adv-PSR"
    )

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
        
        input=$directory/collagen.ome.tiff
        output=$directory/graph.gexf

        # Run your Python CLI script (replace 'your_script.py' with the actual script)
        python3 mask_to_net.py -i "$input" -o "$output"
    else
        echo "Directory not found: $directory"
    fi
    i=$((i+1))
done