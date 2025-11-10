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

# Workflow to run: "decon", "seg", or "both"
WORKFLOW="decon"

# Development mode: mount local code for live editing (true/false)
# When true, mounts local python/, stain_color_map/, and dependency/ directories
# This allows testing code changes without rebuilding the container
DEV_MODE="false"

# Path to local repository (only used if DEV_MODE="true")
LOCAL_REPO_DIR="/users/kir-fritzsche/oyk357/projects/Histology-Collagen-Quantification"

# SLURM resource configuration
PARTITION="short"           # Queue: short, medium, long
MEM="32G"                   # Memory allocation
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

    # Build dev mount string for python, dependency, and optionally stain_color_map
    DEV_MOUNT=",$LOCAL_REPO_DIR/python:/app/python"

    if [[ -d "$LOCAL_REPO_DIR/dependency" ]]; then
        DEV_MOUNT="$DEV_MOUNT,$LOCAL_REPO_DIR/dependency:/app/dependency"
    fi

    # If using local stain map, override STAIN_MOUNT
    if [[ -d "$LOCAL_REPO_DIR/stain_color_map" ]]; then
        STAIN_MOUNT=",$LOCAL_REPO_DIR/stain_color_map:/app/stain_color_map"
    fi

    echo "  Mounting: $LOCAL_REPO_DIR/python -> /app/python"
    [[ -d "$LOCAL_REPO_DIR/dependency" ]] && echo "  Mounting: $LOCAL_REPO_DIR/dependency -> /app/dependency"
    [[ -d "$LOCAL_REPO_DIR/stain_color_map" ]] && echo "  Mounting: $LOCAL_REPO_DIR/stain_color_map -> /app/stain_color_map"
fi

# =============================================================================
# Build bind mount string
# =============================================================================

BIND_MOUNTS="$DATA_DIR:/data${CONFIG_MOUNT}${STAIN_MOUNT}${DEV_MOUNT}"

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
    *)
        echo "Error: Unknown workflow '$WORKFLOW'. Use 'decon', 'seg', or 'both'"
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
