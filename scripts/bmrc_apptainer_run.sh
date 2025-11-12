#!/bin/bash
#
# BMRC Apptainer Job Submission Script
# Runs collagen quantification pipeline on Oxford BMRC cluster
#
# Usage:
#   1. Edit configuration variables below
#   2. Run: bash scripts/bmrc_apptainer_run.sh
#
# Development Mode:
#   Set DEV_MODE="true" to mount local code directories into the container.
#   This allows you to test code changes without rebuilding the SIF image.
#   Mounts: python/, dependency/, stain_color_map/ from LOCAL_REPO_DIR
#

set -e  # Exit on error

# =============================================================================
# Configuration - Edit these paths for your data
# =============================================================================

# Path to your Apptainer/Singularity image
SIF_IMAGE="$HOME/images/collagen-quant.sif"

# Path to your input data directory (histology images)
DATA_DIR="/well/kir-fritzsche/projects/archive/Nan/Nan_Fast_Green_PSR_Staining/split_scene"

# Path to your configs directory
CONFIG_DIR="/users/kir-fritzsche/oyk357/projects/Histology-Collagen-Quantification/configs"

# Path to stain color map directory
STAIN_MAP_DIR="/gpfs3/well/kir-fritzsche/projects/Histology-Collagen-Quantification/stain_color_map"

# =============================================================================
# Interactive Configuration
# =============================================================================

# Prompt for development mode (Python source override)
echo ""
echo "================================================================"
echo "Development Mode Configuration"
echo "================================================================"
echo "Do you want to override container code with local Python source?"
echo "(Use this for testing code changes without rebuilding the container)"
echo ""
read -p "Enable development mode? [y/N]: " -n 1 -r DEV_MODE
echo ""

PYTHON_SRC_DIR=""
if [[ $DEV_MODE =~ ^[Yy]$ ]]; then
    DEFAULT_SRC="/users/kir-fritzsche/oyk357/projects/Histology-Collagen-Quantification/python"
    read -p "Enter path to Python source directory [$DEFAULT_SRC]: " PYTHON_SRC_INPUT
    PYTHON_SRC_DIR="${PYTHON_SRC_INPUT:-$DEFAULT_SRC}"
    echo "Development mode enabled: $PYTHON_SRC_DIR"
else
    echo "Using code baked into the container"
fi

# Prompt for workflow selection
echo ""
echo "================================================================"
echo "Workflow Selection"
echo "================================================================"
echo "Available workflows:"
echo "  1) decon         - Color deconvolution only"
echo "  2) seg           - Segmentation only (requires existing PSR output)"
echo "  3) both          - Run deconvolution then segmentation"
echo "  4) debug         - Debug single tile with diagnostics"
echo "  5) pytest-czi    - Run pytest regression for parallel CZI loading"
echo "  6) benchmark-czi - Benchmark CZI loading with different parallel strategies"
echo "  7) profile-czi   - Profile CZI loading to identify bottlenecks"
echo ""
read -p "Select workflow [1-7, default=1]: " WORKFLOW_CHOICE

case "$WORKFLOW_CHOICE" in
    2)
        WORKFLOW="seg"
        ;;
    3)
        WORKFLOW="both"
        ;;
    4)
        WORKFLOW="debug"
        ;;
    5)
        WORKFLOW="pytest-czi"
        ;;
    6)
        WORKFLOW="benchmark-czi"
        ;;
    7)
        WORKFLOW="profile-czi"
        ;;
    *)
        WORKFLOW="decon"
        ;;
esac

echo "Selected workflow: $WORKFLOW"
echo ""

# Development mode: mount local code for live editing (true/false)
# When true, mounts local python/, stain_color_map/, and dependency/ directories
# This allows testing code changes without rebuilding the container
DEV_MODE="false"

# Path to local repository (only used if DEV_MODE="true")
LOCAL_REPO_DIR="/users/kir-fritzsche/oyk357/projects/Histology-Collagen-Quantification"

# SLURM resource configuration
PARTITION="short"           # Queue: short, medium, long
MEM="128G"                   # Memory allocation
CPUS="8"                    # CPU cores
TIME="1-06:00:00"           # Time limit (D-HH:MM:SS)

# =============================================================================
# Validation
# =============================================================================

if [[ ! -f "$SIF_IMAGE" ]]; then
    echo "Error: SIF image not found at $SIF_IMAGE"
    echo "Please build the image first (see doc/installation.md)"
    exit 1
fi

if [[ ! -d "$DATA_DIR" ]]; then
    echo "Error: Data directory not found at $DATA_DIR"
    echo "Please update DATA_DIR in this script"
    exit 1
fi

if [[ ! -d "$CONFIG_DIR" ]]; then
    echo "Warning: Config directory not found at $CONFIG_DIR"
    echo "Using container's default configs"
    CONFIG_MOUNT=""
else
    CONFIG_MOUNT=",$CONFIG_DIR:/app/configs"
fi

if [[ ! -d "$STAIN_MAP_DIR" ]]; then
    echo "Warning: Stain map directory not found at $STAIN_MAP_DIR"
    STAIN_MOUNT=""
else
    STAIN_MOUNT=",$STAIN_MAP_DIR:/app/stain_color_map"
fi

# Development mode validation and setup
DEV_MOUNT=""
if [[ "$DEV_MODE" == "true" ]]; then
    echo "Development mode enabled - mounting local code directories"

    if [[ ! -d "$LOCAL_REPO_DIR" ]]; then
        echo "Error: Local repository not found at $LOCAL_REPO_DIR"
        echo "Please update LOCAL_REPO_DIR in this script"
        exit 1
    fi

    # Validate required directories exist
    if [[ ! -d "$LOCAL_REPO_DIR/python" ]]; then
        echo "Error: python/ directory not found in $LOCAL_REPO_DIR"
        exit 1
    fi

    # Build dev mount string for python, dependency, benchmark, and optionally stain_color_map
    DEV_MOUNT=",$LOCAL_REPO_DIR/python:/app/python"

    if [[ -d "$LOCAL_REPO_DIR/dependency" ]]; then
        DEV_MOUNT="$DEV_MOUNT,$LOCAL_REPO_DIR/dependency:/app/dependency"
    fi

    if [[ -d "$LOCAL_REPO_DIR/benchmark" ]]; then
        DEV_MOUNT="$DEV_MOUNT,$LOCAL_REPO_DIR/benchmark:/app/benchmark"
    fi

    # If using local stain map, override STAIN_MOUNT
    if [[ -d "$LOCAL_REPO_DIR/stain_color_map" ]]; then
        STAIN_MOUNT=",$LOCAL_REPO_DIR/stain_color_map:/app/stain_color_map"
    fi

    echo "  Mounting: $LOCAL_REPO_DIR/python -> /app/python"
    [[ -d "$LOCAL_REPO_DIR/dependency" ]] && echo "  Mounting: $LOCAL_REPO_DIR/dependency -> /app/dependency"
    [[ -d "$LOCAL_REPO_DIR/benchmark" ]] && echo "  Mounting: $LOCAL_REPO_DIR/benchmark -> /app/benchmark"
    [[ -d "$LOCAL_REPO_DIR/stain_color_map" ]] && echo "  Mounting: $LOCAL_REPO_DIR/stain_color_map -> /app/stain_color_map"
fi

# =============================================================================
# Build bind mount string
# =============================================================================

# Add Python source override if in development mode
BENCHMARK_MOUNT=""
if [[ -n "$PYTHON_SRC_DIR" ]]; then
    if [[ ! -d "$PYTHON_SRC_DIR" ]]; then
        echo "Warning: Python source directory not found at $PYTHON_SRC_DIR"
        PYTHON_MOUNT=""
    else
        PYTHON_MOUNT=",$PYTHON_SRC_DIR:/app/python"

        # Also mount benchmark directory if it exists alongside python source
        BENCHMARK_DIR="$(dirname "$PYTHON_SRC_DIR")/benchmark"
        if [[ -d "$BENCHMARK_DIR" ]]; then
            BENCHMARK_MOUNT=",$BENCHMARK_DIR:/app/benchmark"
        fi
    fi
else
    PYTHON_MOUNT=""
fi

BIND_MOUNTS="$DATA_DIR:/data${CONFIG_MOUNT}${STAIN_MOUNT}${PYTHON_MOUNT}${BENCHMARK_MOUNT}"

# =============================================================================
# Submit job
# =============================================================================

echo "================================================================"
echo "BMRC Apptainer Job Submission"
echo "================================================================"
echo "SIF Image:    $SIF_IMAGE"
echo "Data Dir:     $DATA_DIR"
echo "Config Dir:   $CONFIG_DIR"
echo "Stain Map:    $STAIN_MAP_DIR"
if [[ -n "$PYTHON_SRC_DIR" ]]; then
    echo "Python Src:   $PYTHON_SRC_DIR (DEVELOPMENT MODE)"
    [[ -n "$BENCHMARK_MOUNT" ]] && echo "Benchmark:    $BENCHMARK_DIR (mounted)"
else
    echo "Python Src:   [Using container code]"
fi
echo "Workflow:     $WORKFLOW"
echo "Dev Mode:     $DEV_MODE"
[[ "$DEV_MODE" == "true" ]] && echo "Local Repo:   $LOCAL_REPO_DIR"
echo "Resources:    ${MEM} memory, ${CPUS} CPUs, ${TIME} time limit"
echo "Partition:    $PARTITION"
echo "Bind Mounts:  $BIND_MOUNTS"
echo "================================================================"
echo ""

# Determine which workflow command to run
case "$WORKFLOW" in
    decon)
        CMD="bash python/decon.sh"
        ;;
    seg)
        CMD="bash python/seg.sh"
        ;;
    both)
        CMD="bash python/decon.sh && bash python/seg.sh"
        ;;
    debug)
        CMD="bash python/debug_decon.sh"
        ;;
    pytest-czi)
        CMD="pytest dependency/pyHisto/tests/test_read_czi.py -k parallel_subset -vv"
        ;;
    benchmark-czi)
        CMD="bash benchmark/benchmark_czi.sh"
        ;;
    profile-czi)
        CMD="bash benchmark/profile_czi.sh"
        ;;
    *)
        echo "Error: Unknown workflow '$WORKFLOW'. Use 'decon', 'seg', 'both', 'debug', 'pytest-czi', 'benchmark-czi', or 'profile-czi'"
        exit 1
        ;;
esac

# Submit via srun with interactive PTY
echo "Submitting interactive job to SLURM..."
echo "Command: srun -p $PARTITION --mem=$MEM --cpus-per-task=$CPUS --time=$TIME --pty \\"
echo "         apptainer exec --bind '$BIND_MOUNTS' --pwd /app \\"
echo "         '$SIF_IMAGE' $CMD"
echo ""

srun -p "$PARTITION" \
     --mem="$MEM" \
     --cpus-per-task="$CPUS" \
     --time="$TIME" \
     --pty \
     apptainer exec \
     --bind "$BIND_MOUNTS" \
     --pwd /app \
     "$SIF_IMAGE" \
     $CMD

echo ""
echo "================================================================"
echo "Job completed successfully!"
echo "Output files written to: $DATA_DIR"
echo "================================================================"
