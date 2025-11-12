#!/bin/bash
#
# BMRC Apptainer Image Build Script
# Builds Apptainer/Singularity image for Oxford BMRC cluster
#
# This script provides two build methods:
#   1. From apptainer.def directly on BMRC (Recommended - Default) - native Apptainer format, most reliable
#   2. From existing Docker image (.tar.gz archive) - faster if Docker image already built
#
# Usage:
#   bash scripts/build_hpc_image.sh
#

set -e  # Exit on error

# =============================================================================
# Configuration
# =============================================================================

IMAGE_NAME="collagen-quant"
OUTPUT_SIF="$HOME/images/${IMAGE_NAME}.sif"
# BMRC scratch directory (kir-fritzsche group)
SCRATCH_BUILD_DIR="/well/kir/scratch/kir-fritzsche/apptainer_build/$USER"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "${GREEN}================================================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}================================================================${NC}"
}

print_step() {
    echo -e "${YELLOW}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}$1${NC}"
}

# =============================================================================
# Build Method Selection
# =============================================================================

print_header "BMRC Apptainer Image Build"
echo ""
echo "This script provides two build methods:"
echo ""
echo "  1) From apptainer.def (Recommended)"
echo "     - Builds directly on BMRC using native Apptainer format"
echo "     - No local Docker required"
echo "     - Most reliable method for HPC systems"
echo "     - Build time: 20-40 minutes"
echo ""
echo "  2) From Docker archive (.tar.gz)"
echo "     - Requires pre-built Docker image on local machine"
echo "     - Faster if you already have a Docker image"
echo "     - Requires file transfer to BMRC"
echo ""

read -p "Select build method [1-2, default=1]: " BUILD_METHOD

case "$BUILD_METHOD" in
    2)
        BUILD_TYPE="archive"
        ;;
    *)
        BUILD_TYPE="apptainer_def"
        ;;
esac

echo ""
print_info "Selected build method: $BUILD_TYPE"
echo ""

# =============================================================================
# Validate Prerequisites
# =============================================================================

print_step "Checking prerequisites..."

# Check if running on BMRC
if [[ ! -d "/well" ]] && [[ ! -d "/gpfs3/well" ]]; then
    print_error "This script must be run on the BMRC cluster"
    exit 1
fi

# Check apptainer is available
if ! command -v apptainer &> /dev/null; then
    print_error "apptainer command not found"
    echo "Please load the apptainer module: module load Apptainer"
    exit 1
fi

print_success "Prerequisites OK"
echo ""

# =============================================================================
# Setup Build Environment
# =============================================================================

print_step "Setting up build environment..."

# Create output directory
OUTPUT_DIR=$(dirname "$OUTPUT_SIF")
mkdir -p "$OUTPUT_DIR"

# Check if BMRC scratch directory is accessible
SCRATCH_BASE="/well/kir/scratch/kir-fritzsche"
if [[ -d "$SCRATCH_BASE" ]] && [[ -w "$SCRATCH_BASE" ]]; then
    # Create user subdirectory in scratch
    mkdir -p "$SCRATCH_BUILD_DIR" 2>/dev/null || true
fi

# If scratch directory doesn't exist or isn't writable, use alternative location
if [[ ! -d "$SCRATCH_BUILD_DIR" ]] || [[ ! -w "$SCRATCH_BUILD_DIR" ]]; then
    print_error "BMRC scratch directory not accessible: $SCRATCH_BUILD_DIR"
    echo ""
    echo "Alternative solutions:"
    echo ""
    echo "1. Check group scratch access:"
    echo "   ls -ld $SCRATCH_BASE"
    echo "   Contact your group admin if you need access"
    echo ""
    echo "2. Use home directory (temporary fix - watch quota limits):"
    echo "   Using ~/tmp/apptainer_build instead"
    echo ""
    read -p "Use ~/tmp/apptainer_build for this build? [Y/n]: " USE_HOME

    if [[ ! $USE_HOME =~ ^[Nn]$ ]]; then
        SCRATCH_BUILD_DIR="$HOME/tmp/apptainer_build"
        print_info "Using alternative build directory: $SCRATCH_BUILD_DIR"
        mkdir -p "$SCRATCH_BUILD_DIR"
    else
        print_error "Cannot proceed without a writable build directory"
        exit 1
    fi
else
    # Create scratch build directory
    mkdir -p "$SCRATCH_BUILD_DIR"
fi

# Setup Apptainer cache in scratch (avoid home quota issues)
export APPTAINER_CACHEDIR="$SCRATCH_BUILD_DIR/cache"
mkdir -p "$APPTAINER_CACHEDIR"

# Set temp directory to scratch
export APPTAINER_TMPDIR="$SCRATCH_BUILD_DIR/tmp"
mkdir -p "$APPTAINER_TMPDIR"

print_success "Build environment ready"
echo "  Output SIF: $OUTPUT_SIF"
echo "  Build dir:  $SCRATCH_BUILD_DIR"
echo "  Cache dir:  $APPTAINER_CACHEDIR"
echo ""

# =============================================================================
# Build Method: From Docker Archive
# =============================================================================

if [[ "$BUILD_TYPE" == "archive" ]]; then
    print_header "Building from Docker Archive"
    echo ""

    # Prompt for archive location
    # Default to common BMRC archive location
    DEFAULT_ARCHIVE="/users/kir-fritzsche/oyk357/archive/images/${IMAGE_NAME}.tar.gz"
    read -p "Enter path to Docker archive [$DEFAULT_ARCHIVE]: " ARCHIVE_INPUT
    ARCHIVE_PATH="${ARCHIVE_INPUT:-$DEFAULT_ARCHIVE}"

    # Validate archive exists
    if [[ ! -f "$ARCHIVE_PATH" ]]; then
        print_error "Archive not found at $ARCHIVE_PATH"
        echo ""
        echo "To create the archive on your local machine, run:"
        echo "  bash scripts/build_docker_image.sh"
        echo "  scp ${IMAGE_NAME}.tar.gz user@bmrc:/users/kir-fritzsche/oyk357/archive/images/"
        exit 1
    fi

    print_success "Found archive at $ARCHIVE_PATH"
    echo ""

    # Extract tar.gz to scratch
    print_step "Extracting archive to scratch..."
    TAR_FILE="$SCRATCH_BUILD_DIR/${IMAGE_NAME}.tar"
    gunzip -c "$ARCHIVE_PATH" > "$TAR_FILE"
    print_success "Archive extracted to $TAR_FILE"
    echo ""

    # Build SIF from tar archive
    print_step "Building Apptainer SIF image..."
    print_info "This may take 10-20 minutes depending on image size..."
    echo ""

    apptainer build "$OUTPUT_SIF" "docker-archive://$TAR_FILE"

    # Cleanup
    print_step "Cleaning up temporary files..."
    rm -f "$TAR_FILE"
    print_success "Cleanup complete"
    echo ""

# =============================================================================
# Build Method: From apptainer.def
# =============================================================================

elif [[ "$BUILD_TYPE" == "apptainer_def" ]]; then
    print_header "Building from apptainer.def"
    echo ""

    # Determine repository directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

    print_info "Repository directory: $REPO_DIR"
    echo ""

    # Validate apptainer.def exists
    if [[ ! -f "$REPO_DIR/apptainer.def" ]]; then
        print_error "apptainer.def not found at $REPO_DIR/apptainer.def"
        exit 1
    fi

    # Check git submodules
    print_step "Checking git submodules..."
    if [[ ! -d "$REPO_DIR/dependency/pyHisto/.git" ]]; then
        print_error "pyHisto submodule not initialized"
        echo ""
        echo "Please run from repository root:"
        echo "  git submodule update --init --recursive"
        exit 1
    fi
    print_success "Git submodules initialized"
    echo ""

    # Build SIF from apptainer.def
    print_step "Building Apptainer SIF image from apptainer.def..."
    print_info "This may take 20-40 minutes for first build..."
    print_info "Subsequent builds will be faster due to layer caching"
    echo ""

    # Change to repository directory for build context
    cd "$REPO_DIR"

    # Build using fakeroot (no sudo required on BMRC)
    print_info "Building with --fakeroot..."
    echo ""

    if apptainer build --fakeroot "$OUTPUT_SIF" apptainer.def; then
        print_success "Build completed successfully"
    else
        print_error "Build failed"
        echo ""
        echo "Troubleshooting steps:"
        echo ""
        echo "1. Check if fakeroot is enabled for your account:"
        echo "   Contact BMRC support if you get 'fakeroot not allowed' errors"
        echo ""
        echo "2. Check disk space:"
        echo "   df -h ~"
        echo "   df -h /well/kir/scratch/kir-fritzsche"
        echo ""
        echo "3. Clear Apptainer cache and try again:"
        echo "   rm -rf $APPTAINER_CACHEDIR/*"
        echo "   apptainer cache clean"
        echo ""
        exit 1
    fi
    echo ""
fi

# =============================================================================
# Validation and Summary
# =============================================================================

print_header "Build Complete"
echo ""

if [[ -f "$OUTPUT_SIF" ]]; then
    FILE_SIZE=$(du -h "$OUTPUT_SIF" | cut -f1)
    print_success "SIF image created successfully"
    echo ""
    echo "Image location: $OUTPUT_SIF"
    echo "Image size:     $FILE_SIZE"
    echo ""

    # Test the image
    print_step "Testing image..."
    if apptainer exec "$OUTPUT_SIF" python -c "import bioio, pyvips, histomicstk, geopandas, pytest; print('All dependencies OK')" 2>/dev/null; then
        print_success "Image validation passed (all dependencies including pytest)"
    else
        print_error "Image validation failed"
        echo "The image was built but dependencies may not be working correctly"
    fi
    echo ""

    print_header "Next Steps"
    echo ""
    echo "To run the workflow, use the bmrc_apptainer_run.sh script:"
    echo ""
    echo "  1. Configure your paths in scripts/bmrc_apptainer_run.sh"
    echo "  2. Run: bash scripts/bmrc_apptainer_run.sh"
    echo ""
    echo "Or run manually with:"
    echo ""
    echo "  srun -p short --mem=128G --cpus-per-task=8 --time=1-06:00:00 --pty \\"
    echo "    apptainer exec --bind /path/to/data:/data --pwd /app \\"
    echo "    $OUTPUT_SIF bash python/decon.sh"
    echo ""
else
    print_error "Build failed - SIF image not created"
    exit 1
fi
