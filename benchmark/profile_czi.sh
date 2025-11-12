#!/bin/bash
#
# Quick profiling script for CZI tile loading
# Identifies bottlenecks in the loading process
#

set -e

# Default paths - auto-detect container vs local execution
if [[ -d "/data" ]] && [[ -n "$(ls -A /data 2>/dev/null)" ]]; then
    # Running in container - use /data path
    DEFAULT_CZI="/data/2025_03_04__11_33__0116-Split Scenes (Write files)-01-Scene-1-ScanRegion0.czi"
else
    # Running locally - use full system path
    DEFAULT_CZI="/well/kir-fritzsche/projects/archive/Nan/Nan_Fast_Green_PSR_Staining/split_scene/2025_03_04__11_33__0116-Split Scenes (Write files)-01-Scene-1-ScanRegion0.czi"
fi

echo ""
echo "================================================================"
echo "CZI Tile Loading Profiler"
echo "================================================================"

# Show execution environment
if [[ -d "/data" ]] && [[ -n "$(ls -A /data 2>/dev/null)" ]]; then
    echo "[Running in container - using /data paths]"
else
    echo "[Running locally - using full system paths]"
fi
echo ""

# Prompt for CZI file
read -p "Enter path to CZI file [$DEFAULT_CZI]: " CZI_INPUT
CZI_FILE="${CZI_INPUT:-$DEFAULT_CZI}"

if [[ ! -f "$CZI_FILE" ]]; then
    echo "Error: File not found: $CZI_FILE"
    exit 1
fi

echo "Selected: $CZI_FILE"
echo ""

# Prompt for max tiles
echo "Number of tiles to profile:"
echo "  1) Quick profile (50 tiles) - ~30 seconds"
echo "  2) Standard profile (100 tiles) - ~1-2 minutes"
echo "  3) Detailed profile (200 tiles) - ~2-4 minutes"
echo ""
read -p "Select option [1-3, default=2]: " PROFILE_CHOICE

case "$PROFILE_CHOICE" in
    1)
        MAX_TILES=50
        ;;
    3)
        MAX_TILES=200
        ;;
    *)
        MAX_TILES=100
        ;;
esac

echo ""
echo "Configuration:"
echo "  CZI file: $CZI_FILE"
echo "  Max tiles: $MAX_TILES"
echo ""
echo "Starting profiler..."
echo ""

# Generate output filename
BASENAME=$(basename "$CZI_FILE" .czi)
OUTPUT_FILE="/data/profile_${BASENAME}_${MAX_TILES}tiles.txt"

echo "Results will be saved to: $OUTPUT_FILE"
echo ""

# Run profiler - display output and save to file
python benchmark/profile_czi_loading.py \
    "$CZI_FILE" \
    --max-tiles "$MAX_TILES" | tee "$OUTPUT_FILE"

echo ""
echo "================================================================"
echo "Profiling complete!"
echo "Results saved to: $OUTPUT_FILE"
echo "================================================================"
