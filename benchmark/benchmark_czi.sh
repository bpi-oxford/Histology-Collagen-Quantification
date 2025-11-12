#!/bin/bash
#
# Quick benchmark script for CZI tile loading performance
# Run this via BMRC apptainer or locally
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
echo "CZI Tile Loading Benchmark"
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

# Prompt for test mode
echo "Test modes:"
echo "  1) Quick test (100 tiles, 3 configs) - ~2-5 minutes"
echo "  2) Medium test (500 tiles, all configs) - ~10-20 minutes"
echo "  3) Full benchmark (all tiles, all configs) - may take hours!"
echo ""
read -p "Select test mode [1-3, default=1]: " TEST_MODE

MAX_TILES=""
QUICK_FLAG=""

case "$TEST_MODE" in
    2)
        MAX_TILES="--max-tiles 500"
        ;;
    3)
        MAX_TILES=""
        ;;
    *)
        MAX_TILES="--max-tiles 100"
        QUICK_FLAG="--quick"
        ;;
esac

# Output file with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Save to /data if it exists (inside container), otherwise current directory
if [[ -d "/data" ]]; then
    OUTPUT_FILE="/data/benchmark_results_${TIMESTAMP}.json"
else
    OUTPUT_FILE="benchmark_results_${TIMESTAMP}.json"
fi

echo ""
echo "Configuration:"
echo "  CZI file: $CZI_FILE"
echo "  Max tiles: ${MAX_TILES:-all tiles}"
echo "  Quick mode: ${QUICK_FLAG:-no}"
echo "  Output: $OUTPUT_FILE"
echo ""
echo "Starting benchmark..."
echo ""

# Run benchmark
python benchmark/benchmark_czi_loading.py \
    "$CZI_FILE" \
    $MAX_TILES \
    $QUICK_FLAG \
    --output "$OUTPUT_FILE"

echo ""
echo "================================================================"
echo "Benchmark complete!"
echo "Results saved to: $OUTPUT_FILE"
echo "================================================================"
