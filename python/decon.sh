#!/usr/bin/env bash

# Interactive Color Deconvolution Batch Processing Script
# Processes PSR+FG stained histology images with user-guided input

set -e  # Exit on any error

# Supported file extensions
extensions=("ome.tif" "ome.tiff" "czi" "tif" "tiff")

# Configuration directory
CONFIG_DIR="./configs/decon"
DEFAULT_CONFIG="default.toml"

echo "================================================="
echo "   PSR+FG Color Deconvolution Batch Processor   "
echo "================================================="
echo

# Function to validate directory
validate_directory() {
    local dir="$1"
    if [[ ! -d "$dir" ]]; then
        echo "Error: Directory '$dir' does not exist!"
        return 1
    fi
    return 0
}

# Function to validate file
validate_file() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo "Error: File '$file' does not exist!"
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
# PSR+FG Color Deconvolution Configuration
# Generated: $(date)

[deconvolution]
# Path to input data directory containing histology images
data_dir = ""

# Path to stain color map JSON file
stain_map = "./stain_color_map/stain_vector_map_sample.json"

# Scaling factor (1 = full resolution, 2 = half resolution, etc.)
# Recommended: 2 for large images, 1 for small images
scaling = 2

# Use manual annotation masks (GeoJSON format)
# Manual masks should have the same filename as images
manual_mask = false

# Batch size for parallel processing (higher = more memory usage)
batch_size = 16

[metadata]
description = "Default PSR+FG color deconvolution configuration"
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
    STAIN_COLOR_MAP=$(grep -E '^\s*stain_map\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[" ]//g' | xargs)
    SCALING=$(grep -E '^\s*scaling\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[ ]//g')
    BATCH_NUM=$(grep -E '^\s*batch_size\s*=' "$config_file" | cut -d'=' -f2 | sed 's/[ ]//g')

    # Parse boolean manual_mask
    local manual_mask_val=$(grep -E '^\s*manual_mask\s*=' "$config_file" | sed -E 's/^\s*manual_mask\s*=\s*(true|false).*/\1/')
    if [[ "$manual_mask_val" == "true" ]]; then
        MANUAL_MASK="true"
    else
        MANUAL_MASK="false"
    fi
    
    # Set defaults if parsing failed
    SCALING=${SCALING:-2}
    BATCH_NUM=${BATCH_NUM:-16}
    MANUAL_MASK=${MANUAL_MASK:-false}
    
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

# Function to list available stain maps
list_stain_maps() {
    echo "Available stain color maps in ./stain_color_map/:"
    if ls ./stain_color_map/*.json 1> /dev/null 2>&1; then
        for file in ./stain_color_map/*.json; do
            echo "  - $(basename "$file")"
        done
    else
        echo "  No JSON files found in ./stain_color_map/"
    fi
    echo
}

# Function to save current settings as config
save_current_config() {
    local config_name="$1"
    local config_file="$CONFIG_DIR/${config_name}.toml"
    
    ensure_config_dir
    
    cat > "$config_file" << EOF
# PSR+FG Color Deconvolution Configuration
# Saved: $(date)

[deconvolution]
data_dir = "$DATA_DIR"
stain_map = "$STAIN_COLOR_MAP"
scaling = $SCALING
manual_mask = $MANUAL_MASK
batch_size = $BATCH_NUM

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
        echo "Enter the path to your input data directory:"
        echo "Example: /mnt/Data/Jacky/Nan/250213_1st Bleo Expt/split_scene"
        read -r DATA_DIR
        
        if validate_directory "$DATA_DIR"; then
            break
        fi
        echo "Please enter a valid directory path."
        echo
    done

    # Prompt for stain color map
    list_stain_maps
    while true; do
        echo "Enter the path to your stain color map JSON file:"
        echo "Example: ./stain_color_map/stain_vector_map_sample.json"
        read -r STAIN_COLOR_MAP
        
        if validate_file "$STAIN_COLOR_MAP"; then
            break
        fi
        echo "Please enter a valid file path."
        echo
    done

    # Prompt for scaling factor
    echo "Enter scaling factor (1 = full resolution, 2 = half resolution, etc.):"
    echo "Recommended: 2 for large images, 1 for small images"
    echo "Default: 2"
    read -r input_scaling
    SCALING=${input_scaling:-2}

    # Prompt for manual mask usage
    echo
    echo "Do you want to use manual annotation masks? (y/n)"
    echo "Note: Manual masks should be in GeoJSON format with the same filename as your images"
    echo "Default: n"
    read -r use_manual_mask
    if [[ "$use_manual_mask" =~ ^[Yy]$ ]]; then
        MANUAL_MASK="true"
    else
        MANUAL_MASK="false"
    fi

    # Prompt for batch number
    echo
    echo "Enter batch size for parallel processing (higher = more memory usage):"
    echo "Default: 16"
    read -r input_batch
    BATCH_NUM=${input_batch:-16}
fi

# Validate data directory and stain map (whether from config or interactive)
if ! validate_directory "$DATA_DIR"; then
    echo "Error: Invalid data directory: $DATA_DIR"
    exit 1
fi

if ! validate_file "$STAIN_COLOR_MAP"; then
    echo "Error: Invalid stain map file: $STAIN_COLOR_MAP"
    exit 1
fi

echo
echo "=== Configuration Summary ==="
echo "Data directory: $DATA_DIR"
echo "Stain map: $STAIN_COLOR_MAP"
echo "Scaling factor: $SCALING"
echo "Manual masks: $MANUAL_MASK"
echo "Batch size: $BATCH_NUM"
echo "============================="
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
echo "Proceed with processing? (Y/n)"
read -r confirm
confirm=${confirm:-Y}  # Default to Y if empty
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Processing cancelled."
    exit 0
fi

echo
echo "Scanning for supported image files..."

# Find and catalog images
input_files=()
output_dirs=()
image_count=0

for file in "$DATA_DIR"/*; do
    if [[ -f "$file" ]]; then
        for ext in "${extensions[@]}"; do
            if [[ "$file" == *.$ext ]]; then
                filename=$(basename "$file")
                filename_no_suffix="$(basename "$filename" .$ext)"
                output_dir="$DATA_DIR/$filename_no_suffix"
                input_files+=("$file")
                output_dirs+=("$output_dir")
                image_count=$((image_count + 1))
                echo "  Found: $filename"
                break
            fi
        done
    fi
done

if [[ $image_count -eq 0 ]]; then
    echo "No supported image files found in '$DATA_DIR'"
    echo "Supported extensions: ${extensions[*]}"
    exit 1
fi

echo "Found $image_count image(s) to process"
echo
echo "Starting batch processing..."
echo

# Process images
processed=0
failed=0

for ((i=0; i<${#input_files[@]}; i++)); do
    input_file="${input_files[$i]}"
    output_dir="${output_dirs[$i]}"
    processed=$((processed + 1))
    
    echo "[$processed/$image_count] Processing: $(basename "$input_file")"
    echo "  → Output directory: $(basename "$output_dir")"
    
    # Create output directory
    mkdir -p "$output_dir"
    
    # Prepare arguments
    decon_args=(-i "$input_file" -o "$output_dir" -s "$SCALING" --stain_map "$STAIN_COLOR_MAP" -bn "$BATCH_NUM")
    
    # Add mask if manual masks are enabled
    if [[ "$MANUAL_MASK" == "true" ]]; then
        mask_file="${input_file%.*}.geojson"
        if [[ -f "$mask_file" ]]; then
            decon_args+=(-m "$mask_file")
            echo "  → Using manual mask: $(basename "$mask_file")"
        else
            echo "  → Warning: Manual mask not found, using automatic tissue detection"
        fi
    fi
    
    # Run processing
    echo "  → Processing..."
    if python ./python/decon.py "${decon_args[@]}" 2>&1; then
        echo "  ✓ Successfully processed!"
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
echo "Total files processed: $image_count"
echo "Successful: $((processed - failed))"
echo "Failed: $failed"

if [[ "$use_interactive" == false && -n "$selected_config" ]]; then
    echo "Configuration used: $(basename "$(dirname "$selected_config")")/$(basename "$selected_config")"
fi

if [[ $failed -gt 0 ]]; then
    echo
    echo "⚠️  Some files failed to process. Check the error messages above."
    echo "Tip: You can create different configurations in $CONFIG_DIR for different processing scenarios."
    exit 1
else
    echo
    echo "🎉 All files processed successfully!"
    echo "You can now proceed to the segmentation step using python/seg.sh"
    if [[ -d "$CONFIG_DIR" ]]; then
        echo "Configuration files are stored in: $CONFIG_DIR"
    fi
    exit 0
fi