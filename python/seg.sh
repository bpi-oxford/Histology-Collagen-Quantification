#!/bin/bash

# Interactive Collagen Segmentation Batch Processing Script
# Processes PSR channels from color deconvolution output to segment collagen

set -e  # Exit on any error

echo "================================================="
echo "    PSR Collagen Segmentation Batch Processor   "
echo "================================================="
echo

# Configuration directory
CONFIG_DIR="./configs/seg"
DEFAULT_CONFIG="default.toml"

# Function to validate directory
validate_directory() {
    local dir="$1"
    if [[ ! -d "$dir" ]]; then
        echo "Error: Directory '$dir' does not exist!"
        return 1
    fi
    return 0
}

# Function to create config directory if it doesn't exist
ensure_config_dir() {
    if [[ ! -d "$CONFIG_DIR" ]]; then
        echo "Creating configuration directory: $CONFIG_DIR"
        mkdir -p "$CONFIG_DIR"
    fi
}

# Function to generate default TOML config
generate_default_config() {
    local config_file="$1"
    cat > "$config_file" << EOF
# PSR Collagen Segmentation Configuration
# Generated: $(date)

[segmentation]
# Path to processed data directory containing PSR.ome.tiff files
data_dir = ""

# Tile size for regional analysis (pixels)
# Larger tiles = faster processing, smaller tiles = more detailed analysis
# Recommended: 2048 for most images, 1024 for detailed analysis
tile_size = 2048

# Padding/overlap between tiles (pixels)
# Reduces edge artifacts in tiled analysis
# Recommended: 0 for speed, 512 for better edge handling
padding = 0

# Number of classes for multi-level Otsu thresholding
# More classes = more threshold levels for segmentation
# Recommended: 4 for most PSR images
classes = 4

# Otsu threshold class ID for collagen segmentation
# Valid range: 0 to (classes-1)
# 0 = Background (darkest), middle classes = Collagen gradients, highest = Dense collagen (brightest)
# Recommended: 1 for most PSR images when classes=4
class_id = 1

[metadata]
description = "Default PSR collagen segmentation configuration"
created = "$(date -Iseconds)"
version = "1.0"
EOF
    echo "Generated default configuration: $config_file"
}

# Function to parse TOML config file
parse_toml_config() {
    local config_file="$1"
    
    if [[ ! -f "$config_file" ]]; then
        echo "Error: Config file '$config_file' not found!"
        return 1
    fi
    
    # Parse TOML file using basic regex patterns
    DATA_DIR=$(grep -E '^\s*data_dir\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[" ]//g' | xargs)
    TILE=$(grep -E '^\s*tile_size\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[ ]//g')
    PADDING=$(grep -E '^\s*padding\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[ ]//g')
    CLASS=$(grep -E '^\s*class_id\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[ ]//g')
    CLASSES=$(grep -E '^\s*classes\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[ ]//g')

    # Set defaults if parsing failed
    TILE=${TILE:-2048}
    PADDING=${PADDING:-0}
    CLASS=${CLASS:-1}
    CLASSES=${CLASSES:-4}
    
    return 0
}

# Function to list available configs
list_configs() {
    local configs=()
    local count=0
    
    echo "Scanning configuration directory: $CONFIG_DIR"
    echo
    
    if [[ -d "$CONFIG_DIR" ]]; then
        for config_file in "$CONFIG_DIR"/*.toml; do
            if [[ -f "$config_file" ]]; then
                configs+=("$config_file")
                count=$((count + 1))
                local basename=$(basename "$config_file" .toml)
                
                # Try to extract description from config
                local description=""
                if grep -q "^\s*description\s*=" "$config_file" 2>/dev/null; then
                    description=$(grep -E '^\s*description\s*=' "$config_file" | sed -E 's/^\s*description\s*=\s*"([^"]*)".*/\1/' | xargs)
                fi
                
                echo "$count) $basename"
                if [[ -n "$description" ]]; then
                    echo "   Description: $description"
                fi
                echo "   File: $config_file"
                echo
            fi
        done
    fi
    
    if [[ $count -eq 0 ]]; then
        echo "No configuration files found in $CONFIG_DIR"
        return 1
    fi
    
    # Store configs array for later use
    AVAILABLE_CONFIGS=("${configs[@]}")
    return 0
}

# Function to select or create config
select_config() {
    ensure_config_dir
    
    echo "Configuration Management"
    echo "========================"
    
    if list_configs; then
        echo "Select a configuration:"
        echo "0) Create new configuration"
        echo "i) Interactive mode (skip config file)"
        echo
        
        while true; do
            read -r -p "Enter choice (number, 'i' for interactive, or 'q' to quit): " choice
            
            case "$choice" in
                q|Q)
                    echo "Exiting..."
                    exit 0
                    ;;
                i|I)
                    echo "Using interactive mode..."
                    return 1  # Signal to use interactive mode
                    ;;
                0)
                    # Create new config
                    echo
                    read -r -p "Enter name for new configuration (without .toml extension): " config_name
                    if [[ -z "$config_name" ]]; then
                        echo "Invalid config name!"
                        continue
                    fi
                    
                    local new_config="$CONFIG_DIR/${config_name}.toml"
                    generate_default_config "$new_config"
                    echo
                    echo "Please edit the configuration file and run the script again:"
                    echo "  $new_config"
                    exit 0
                    ;;
                ''|*[!0-9]*)
                    echo "Please enter a valid number, 'i', or 'q'"
                    ;;
                *)
                    if [[ "$choice" -gt 0 && "$choice" -le "${#AVAILABLE_CONFIGS[@]}" ]]; then
                        selected_config="${AVAILABLE_CONFIGS[$((choice-1))]}"
                        echo "Selected configuration: $(basename "$selected_config")"
                        
                        if parse_toml_config "$selected_config"; then
                            # Validate data_dir from config
                            if [[ -z "$DATA_DIR" ]]; then
                                echo
                                echo "Error: data_dir is not set in the configuration file!"
                                echo "Please edit: $selected_config"
                                exit 1
                            fi
                            return 0  # Success
                        else
                            echo "Error parsing configuration file!"
                            exit 1
                        fi
                    else
                        echo "Please enter a number between 0 and ${#AVAILABLE_CONFIGS[@]}"
                    fi
                    ;;
            esac
        done
    else
        # No configs found
        echo "Would you like to:"
        echo "1) Create a default configuration file"
        echo "2) Use interactive mode"
        echo
        
        while true; do
            read -r -p "Enter choice (1-2): " choice
            case "$choice" in
                1)
                    local default_config_path="$CONFIG_DIR/$DEFAULT_CONFIG"
                    generate_default_config "$default_config_path"
                    echo
                    echo "Please edit the configuration file and run the script again:"
                    echo "  $default_config_path"
                    exit 0
                    ;;
                2)
                    echo "Using interactive mode..."
                    return 1  # Signal to use interactive mode
                    ;;
                *)
                    echo "Please enter 1 or 2"
                    ;;
            esac
        done
    fi
}

# Function to check if directory contains processed data
check_processed_data() {
    local dir="$1"
    local psr_count=0
    local mask_count=0
    
    for subdir in "$dir"/*/; do
        if [[ -d "$subdir" ]]; then
            if [[ -f "$subdir/PSR.ome.tiff" ]]; then
                psr_count=$((psr_count + 1))
            fi
            if [[ -f "$subdir/mask.ome.tiff" ]]; then
                mask_count=$((mask_count + 1))
            fi
        fi
    done
    
    echo "Found $psr_count PSR files and $mask_count mask files"
    
    if [[ $psr_count -eq 0 ]]; then
        echo "Error: No PSR.ome.tiff files found in subdirectories of '$dir'"
        echo "Make sure you have run the color deconvolution step first (python/decon.sh)"
        return 1
    fi
    
    return 0
}

# Function to save current settings as config
save_current_config() {
    local config_name="$1"
    local config_file="$CONFIG_DIR/${config_name}.toml"
    
    ensure_config_dir
    
    cat > "$config_file" << EOF
# PSR Collagen Segmentation Configuration
# Saved: $(date)

[segmentation]
data_dir = "$DATA_DIR"
tile_size = $TILE
padding = $PADDING
class_id = $CLASS
classes = $CLASSES

[metadata]
description = "Configuration saved from interactive session"
created = "$(date -Iseconds)"
version = "1.0"
EOF
    echo "Configuration saved to: $config_file"
}

# Try to load configuration, fallback to interactive mode
use_interactive=false
selected_config=""
if select_config; then
    echo "Using configuration file settings"
else
    use_interactive=true
    echo "Using interactive mode"
fi

# Interactive mode for parameters
if [[ "$use_interactive" == true ]]; then
    # Prompt for data directory
    while true; do
        echo "Enter the path to your processed data directory:"
        echo "This should contain subdirectories with PSR.ome.tiff and mask.ome.tiff files"
        echo "Example: /mnt/Data/Jacky/Nan/250213_1st Bleo Expt/split_scene"
        read -r DATA_DIR
        
        if validate_directory "$DATA_DIR"; then
            if check_processed_data "$DATA_DIR"; then
                break
            fi
        fi
        echo "Please enter a valid directory path with processed data."
        echo
    done

    # Prompt for tile size
    echo
    echo "Enter tile size for regional analysis (in pixels):"
    echo "Larger tiles = faster processing, smaller tiles = more detailed regional analysis"
    echo "Recommended: 2048 for most images, 1024 for very detailed analysis"
    echo "Default: 2048"
    read -r input_tile
    TILE=${input_tile:-2048}

    # Prompt for padding
    echo
    echo "Enter padding/overlap between tiles (in pixels):"
    echo "Padding reduces edge artifacts in tiled analysis"
    echo "Recommended: 0 for speed, 512 for better edge handling"
    echo "Default: 0"
    read -r input_padding
    PADDING=${input_padding:-0}

    # Prompt for number of classes
    echo
    echo "Enter number of classes for multi-level Otsu thresholding:"
    echo "More classes = more threshold levels for segmentation"
    echo "Recommended: 4 for most PSR images"
    echo "Default: 4"
    read -r input_classes
    CLASSES=${input_classes:-4} 

    # Prompt for class selection
    echo
    echo "Enter Otsu threshold class ID for collagen segmentation:"
    echo "Valid range: 0 to (classes-1)"
    echo "0 = Background class (darkest)"
    echo "1 = Collagen class (typical choice)"
    echo "2+ = Dense collagen classes (brightest)"
    echo "Recommended: 1 for most PSR images"
    echo "Default: 1"
    read -r input_class
    CLASS=${input_class:-1}

    # Validate class_id is within valid range and re-prompt if needed
    max_class_id=$((CLASSES - 1))
    while [[ $CLASS -lt 0 || $CLASS -gt $max_class_id ]]; do
        echo
        echo "Error: class_id ($CLASS) must be between 0 and $max_class_id (classes-1)"
        echo "Current classes setting: $CLASSES"
        echo "Please enter a valid class_id (0-$max_class_id):"
        read -r input_class
        CLASS=${input_class:-1}
    done
fi

# Validate data directory (whether from config or interactive)
if ! validate_directory "$DATA_DIR"; then
    echo "Error: Invalid data directory: $DATA_DIR"
    exit 1
fi

if ! check_processed_data "$DATA_DIR"; then
    echo "Error: No suitable processed data found in: $DATA_DIR"
    exit 1
fi

echo
echo "=== Configuration Summary ==="
echo "Data directory: $DATA_DIR"
echo "Tile size: $TILE pixels"
echo "Padding: $PADDING pixels"
echo "Class ID: $CLASS"
echo "Classes: $CLASSES"
echo "============================"
echo

# Option to save config if using interactive mode
if [[ "$use_interactive" == true ]]; then
    echo "Would you like to save these settings as a configuration file for future use? (y/n)"
    read -r save_config
    if [[ "$save_config" =~ ^[Yy]$ ]]; then
        echo "Enter a name for this configuration (without .toml extension):"
        read -r config_name
        if [[ -n "$config_name" ]]; then
            save_current_config "$config_name"
            echo
        fi
    fi
fi

# Confirm before processing
echo "Proceed with segmentation? (Y/n)"
read -r confirm
confirm=${confirm:-Y}  # Default to Y if empty
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Processing cancelled."
    exit 0
fi

echo
echo "Scanning for processed directories..."

# Find directories with PSR files
declare -a directories
dir_count=0

for subdir in "$DATA_DIR"/*/; do
    if [[ -d "$subdir" && -f "$subdir/PSR.ome.tiff" ]]; then
        directories+=("$subdir")
        dir_count=$((dir_count + 1))
        echo "  Found: $(basename "$subdir")"
    fi
done

if [[ $dir_count -eq 0 ]]; then
    echo "No directories with PSR.ome.tiff files found!"
    exit 1
fi

echo "Found $dir_count directories to process"
echo
echo "Starting batch segmentation..."
echo

# Process directories
processed=0
failed=0

for directory in "${directories[@]}"; do
    processed=$((processed + 1))
    dir_name=$(basename "$directory")
    
    echo "[$processed/$dir_count] Processing: $dir_name"
    
    # Define file paths
    input="$directory/PSR.ome.tiff"
    output="$directory/collagen.ome.tiff"
    mask="$directory/mask.ome.tiff"
    stat="$directory/res.csv"
    
    # Check required input files
    if [[ ! -f "$input" ]]; then
        echo "  ✗ PSR.ome.tiff not found, skipping"
        failed=$((failed + 1))
        echo
        continue
    fi
    
    echo "  → Input: PSR.ome.tiff"
    echo "  → Output: collagen.ome.tiff"
    echo "  → Statistics: res.csv"
    
    # Check for mask file
    seg_args=(-i "$input" -o "$output" -s "$stat" -t "$TILE" -p "$PADDING" -c "$CLASS" --classes "$CLASSES")
    
    if [[ -f "$mask" ]]; then
        seg_args+=(-m "$mask")
        echo "  → Using tissue mask: mask.ome.tiff"
    else
        echo "  → No tissue mask found, processing entire image"
    fi
    
    # Run segmentation
    echo "  → Segmenting collagen..."
    if python ./python/seg.py "${seg_args[@]}"; then
        echo "  ✓ Successfully processed!"
        
        # Show quick stats if CSV was generated
        if [[ -f "$stat" ]]; then
            if command -v tail >/dev/null 2>&1; then
                echo "  → Quick stats:"
                tail -1 "$stat" | sed 's/^/    /'
            fi
        fi
    else
        echo "  ✗ Processing failed!"
        failed=$((failed + 1))
    fi
    echo
done

# Final summary
echo "================================================="
echo "              Processing Complete                "
echo "================================================="
echo "Total directories processed: $dir_count"
echo "Successful: $((processed - failed))"
echo "Failed: $failed"

if [[ "$use_interactive" == false && -n "$selected_config" ]]; then
    echo "Configuration used: $(basename "$(dirname "$selected_config")")/$(basename "$selected_config")"
fi

if [[ $failed -gt 0 ]]; then
    echo
    echo "⚠️  Some directories failed to process. Check the error messages above."
    echo "Tip: You can create different configurations in $CONFIG_DIR for different processing scenarios."
    exit 1
else
    echo
    echo "🎉 All directories processed successfully!"
    echo "Check the res.csv files in each directory for quantification results."
    if [[ -d "$CONFIG_DIR" ]]; then
        echo "Configuration files are stored in: $CONFIG_DIR"
    fi
    exit 0
fi