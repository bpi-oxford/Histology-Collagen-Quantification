#!/bin/bash
# Build Docker image and export for HPC Apptainer/Singularity conversion
# This script builds the collagen-quant Docker image, saves it as a tar archive,
# and compresses it for transfer to HPC clusters.

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
IMAGE_NAME="collagen-quant"
IMAGE_TAG="latest"
OUTPUT_TAR="collagen-quant.tar"
OUTPUT_GZ="collagen-quant.tar.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Collagen Quantification HPC Image Build ===${NC}"
echo ""

# Step 1: Check for git submodules
echo -e "${YELLOW}Step 1/4: Checking git submodules...${NC}"
if [ ! -d "dependency/pyHisto/.git" ]; then
    echo -e "${RED}Error: pyHisto submodule not initialized${NC}"
    echo "Please run: git submodule update --init --recursive"
    exit 1
fi
echo -e "${GREEN}✓ Git submodules initialized${NC}"
echo ""

# Step 2: Build Docker image
echo -e "${YELLOW}Step 2/4: Building Docker image...${NC}"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker image built successfully${NC}"
echo ""

# Step 3: Save Docker image to tar archive
echo -e "${YELLOW}Step 3/4: Saving Docker image to tar archive...${NC}"
echo "Output: ${OUTPUT_TAR}"
docker save "${IMAGE_NAME}:${IMAGE_TAG}" -o "${OUTPUT_TAR}"
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker save failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker image saved to ${OUTPUT_TAR}${NC}"
echo ""

# Step 4: Compress tar archive
echo -e "${YELLOW}Step 4/4: Compressing tar archive...${NC}"
echo "Output: ${OUTPUT_GZ}"
gzip -f "${OUTPUT_TAR}"
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Compression failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Archive compressed to ${OUTPUT_GZ}${NC}"
echo ""

# Display final information
FILE_SIZE=$(du -h "${OUTPUT_GZ}" | cut -f1)
echo -e "${GREEN}=== Build Complete ===${NC}"
echo "Image archive: ${OUTPUT_GZ}"
echo "File size: ${FILE_SIZE}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Transfer to HPC cluster:"
echo "   scp ${OUTPUT_GZ} user@cluster:~/archive/images"
echo ""
echo "2. On HPC cluster, convert to Apptainer/Singularity:"
echo "   cd ~/archive/images"
echo "   gunzip ${OUTPUT_GZ}"
echo "   apptainer build collagen-quant.sif docker-archive://${OUTPUT_TAR}"
echo ""
