#!/bin/bash
#
# BMRC Apptainer Job Submission Script
# Runs collagen quantification pipeline on Oxford BMRC cluster
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

# =============================================================================
# Build bind mount string
# =============================================================================

BIND_MOUNTS="$DATA_DIR:/data${CONFIG_MOUNT}${STAIN_MOUNT}"

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
