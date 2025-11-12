# Installation Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
  - [Method 1: Docker (Local Build)](#method-1-docker-local-build)
  - [Method 2: Pixi (Local Development)](#method-2-pixi-fastest-for-local-development)
  - [Method 3: Conda (Traditional)](#method-3-conda-traditional)
- [HPC/Cluster Deployment](#hpccluster-deployment)
  - [General HPC Setup](#convert-to-apptainersingularity-hpc)
  - [BMRC Cluster Build](#bmrc-cluster-build)
  - [BMRC Cluster Usage](#bmrc-cluster---automated-script)
  - [Manual SLURM Submission](#manual-slurm-submission)
- [Platform-Specific Notes](#platform-specific-notes)
- [Troubleshooting](#troubleshooting)
- [Verify Installation](#verify-installation)

## Prerequisites

**For all methods:**
- Git with submodule support
- For pyHisto: Access to the Oxford-Zeiss-Centre-of-Excellence/pyHisto repository (SSH key or HTTPS credentials configured)

## Installation Methods

### Method 1: Docker (Local Build)

Build Docker image on your local machine (requires Docker Desktop or Docker Engine):

```bash
# Initialize git submodules (required for pyHisto)
git submodule update --init --recursive

# Build image using automated script
bash scripts/build_docker_image.sh

# Or manually:
docker build -t collagen-quant .

# Test locally
docker run -it --rm -v /path/to/data:/data collagen-quant
docker run -it --rm collagen-quant python -c "import pyvips, geopandas, bioio, histomicstk"
```

**Note:** The Docker build uses the pyHisto git submodule from `dependency/pyHisto` instead of requiring a GITHUB_TOKEN build argument.

**Next steps:**
- For local usage: Run workflows directly with `docker run`
- For HPC deployment: See [HPC/Cluster Deployment](#hpccluster-deployment) section below

## HPC/Cluster Deployment

### Convert to Apptainer/Singularity (HPC)

For general HPC clusters (non-BMRC), use the Docker archive approach:

**On local machine:**
```bash
# Build and export Docker image
bash scripts/build_docker_image.sh

# Transfer to HPC cluster
scp collagen-quant.tar.gz user@cluster:~/archive/images
```

**On HPC cluster:**
```bash
cd ~/archive/images
gunzip collagen-quant.tar.gz  # Extract tar from tar.gz
apptainer build collagen-quant.sif docker-archive://collagen-quant.tar

# Test image
apptainer exec collagen-quant.sif python -c "import bioio, pyvips, histomicstk, geopandas"

# Run workflow with bind mounts
srun -p short --mem=32G --cpus-per-task=8 --time=1-06:00:00 --pty \
  apptainer exec --bind /path/to/data:/data --pwd /app \
  collagen-quant.sif bash python/decon.sh
```

### BMRC Cluster Build

For Oxford BMRC cluster users, there are **two build options**:

#### Option 1: Build from apptainer.def on BMRC (Recommended)

Build directly on BMRC using native Apptainer definition file. This is the most reliable method for BMRC:

**On BMRC cluster - Method A: Using interactive script (recommended):**
```bash
# Run the interactive build script
bash scripts/build_hpc_image.sh

# Press Enter to select default option 1 (apptainer.def)
# The script will:
# - Validate prerequisites and check git submodules
# - Setup build environment and cache directories
# - Build the SIF image (~20-40 minutes)
# - Test the built image
```

**On BMRC cluster - Method B: Direct command:**
```bash
# Load Apptainer module
module load Apptainer

# Ensure git submodules are initialized
git submodule update --init --recursive

# Navigate to repository
cd /gpfs3/well/kir-fritzsche/projects/Histology-Collagen-Quantification

# Build SIF image directly (20-40 minutes)
apptainer build --fakeroot ~/images/collagen-quant.sif apptainer.def

# Test the image
apptainer exec ~/images/collagen-quant.sif python -c "import bioio, pyvips, histomicstk, geopandas, pytest; print('All dependencies OK')"
```

**Advantages:**
- Native Apptainer format - most reliable on HPC
- No Docker required on local machine
- No file transfer needed
- Works on all BMRC systems with Apptainer

**Build time:** 20-40 minutes for first build (cached layers speed up rebuilds)

**Troubleshooting:**
- If `--fakeroot` fails, contact BMRC support to enable fakeroot for your account
- Build uses `/well/kir/scratch/kir-fritzsche/` for cache (falls back to `~/tmp` if unavailable)

#### Option 2: From Docker Archive

Build Docker image on local machine, then convert to Apptainer SIF on BMRC:

**On local machine (with Docker):**
```bash
# Build and export Docker image
bash scripts/build_docker_image.sh

# Transfer to BMRC
scp collagen-quant.tar.gz user@bmrc:/users/kir-fritzsche/oyk357/archive/images/
```

**On BMRC cluster:**
```bash
# Run interactive build script
bash scripts/build_hpc_image.sh

# Follow prompts:
# - Select option 2 (From Docker archive)
# - Default path: /users/kir-fritzsche/oyk357/archive/images/collagen-quant.tar.gz (press Enter to use)
```

The script will:
1. Validate prerequisites (apptainer, BMRC environment)
2. Setup build environment in `/well/kir/scratch/kir-fritzsche/apptainer_build/$USER`
3. Extract Docker archive to scratch
4. Build Apptainer SIF image (~10-20 minutes)
5. Test the built image
6. Output SIF location: `~/images/collagen-quant.sif`

**Advantages:**
- Faster conversion (10-20 minutes vs 20-40 minutes)
- Useful if you already have Docker image locally
- Same image can be tested locally with Docker

**Which option to choose?**
- **Option 1 (apptainer.def)**: Best for BMRC, no Docker needed, most reliable ✅
- **Option 2 (Docker archive)**: Best if you have Docker locally and want faster conversion

### BMRC Cluster - Running Workflows

After building the SIF image, use the automated script for interactive workflow execution:

```bash
bash scripts/bmrc_apptainer_run.sh
```

**Interactive Prompts:**

The script will ask you:

1. **Development Mode**: Override container code with local Python source?
   - `y`: Enable development mode (mount local `python/` directory)
   - `n`: Use code baked into container (default)

2. **Workflow Selection**: Which workflow to run?
   - `1`: Color deconvolution only
   - `2`: Segmentation only (requires existing PSR output)
   - `3`: Both deconvolution and segmentation
   - `4`: Debug mode (single tile with diagnostics)
   - `5`: Run pytest for CZI loading tests

**Configuration (edit in script if needed):**
```bash
nano scripts/bmrc_apptainer_run.sh

# Key variables:
SIF_IMAGE="$HOME/images/collagen-quant.sif"
DATA_DIR="/well/kir-fritzsche/projects/..."
CONFIG_DIR="/users/.../configs"
PARTITION="short"        # SLURM queue
MEM="32G"               # Memory allocation
CPUS="8"                # CPU cores
TIME="1-06:00:00"       # Time limit
```

**Script features:**
- Interactive prompts for workflow and development mode
- Validates all paths before submission
- Auto-configures bind mounts for data, configs, and stain maps
- Submits interactive job via `srun --pty` with specified resources
- Allows responding to workflow prompts in real-time
- Development mode for testing code changes without rebuilding

**Development Mode Details:**

When enabled, development mode:
- Mounts local `python/` directory to `/app/python` in container
- Changes to Python code are immediately reflected
- Useful for debugging, testing fixes, and rapid iteration
- No need to rebuild SIF image for each code change

**Example usage:**
```bash
# Run with development mode
bash scripts/bmrc_apptainer_run.sh
# Answer "y" for development mode
# Provide path: /users/kir-fritzsche/oyk357/projects/Histology-Collagen-Quantification/python
# Select workflow: 1 (decon)
```

### Manual SLURM Submission

For custom workflows, request an interactive session manually:

```bash
# Request interactive session
srun -p short --mem=32G --cpus-per-task=8 --time=1-06:00:00 --pty bash

# Run workflow with bind mounts
apptainer exec --bind /path/to/data:/data,/path/to/configs:/app/configs --pwd /app collagen-quant.sif bash python/decon.sh
```

## Method 2: Pixi (Fastest for Local Development)

```bash
# Install pixi (if needed)
curl -fsSL https://pixi.sh/install.sh | bash

# Initialize git submodules (required for pyHisto)
git submodule update --init --recursive

# Setup environment
pixi install
pixi shell
pip install -e .
pip install -e ./dependency/pyHisto
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

## Method 3: Conda (Traditional)

```bash
# Initialize git submodules (required for pyHisto)
git submodule update --init --recursive

# Create environment
conda env create -f env.yaml
conda activate collagen_quant

# Install package
pip install -e .
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

**Note:** The `env.yaml` includes `requirements.txt` which automatically installs pyHisto from `./dependency/pyHisto` in editable mode.

## Platform-Specific Notes

### Windows
- Requires libvips: run `bash setup_windows.sh` first
- WSL2 recommended for better performance

### macOS/Linux
- libvips installed automatically via conda
- Pixi is fastest setup method

## Troubleshooting

**"pyHisto not found" error:**
```bash
# Ensure git submodules are initialized
git submodule update --init --recursive

# Verify pyHisto exists
ls -la dependency/pyHisto
```

**SSH key issues with pyHisto submodule:**
```bash
# If you don't have SSH access, convert submodule to HTTPS
git config submodule.dependency/pyHisto.url https://github.com/Oxford-Zeiss-Centre-of-Excellence/pyHisto.git
git submodule sync
git submodule update --init --recursive
```

**Docker build fails with GPG errors:**
```bash
docker system prune -f
docker build --no-cache -t collagen-quant .
```

**histomicstk installation fails:**
- Ensure Java JDK is installed (`sudo apt install default-jdk` on Linux)
- Use the explicit install command:
  ```bash
  python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
  ```

**Out of memory during build:**
- Increase Docker memory limit (Docker Desktop → Settings → Resources)
- Use smaller batch sizes in processing

**Apptainer build fails with tar header error:**
- Apptainer's `docker-archive://` requires an uncompressed tar file
- Use the automated build script which handles this automatically:
  ```bash
  bash scripts/build_hpc_image.sh  # Select option 1
  ```
- Or manually:
  - Extract first: `gunzip collagen-quant.tar.gz`
  - Then build: `apptainer build collagen-quant.sif docker-archive://collagen-quant.tar`

**BMRC build script fails with "apptainer command not found":**
```bash
# Load Apptainer module on BMRC
module load Apptainer

# Then run the build script
bash scripts/build_hpc_image.sh
```

**BMRC build fails with "Permission denied" or scratch directory not accessible:**
- The build script needs `/well/kir/scratch/kir-fritzsche/apptainer_build/$USER` for temporary build files
- If this directory isn't accessible, the script will prompt to use `~/tmp/apptainer_build` instead
- **Check group scratch access**:
  ```bash
  # Verify you have access to the group scratch space
  ls -ld /well/kir/scratch/kir-fritzsche

  # If you don't have access, contact your group admin (kir-fritzsche group)
  ```
- **Alternative**: Use home directory for build (watch quota limits):
  ```bash
  # The script will automatically prompt to use ~/tmp/apptainer_build
  # Note: Large build files may fill your home directory quota
  # Accept the prompt with 'Y' to proceed with home directory build
  ```

**Cluster home directory quota exceeded:**
- Apptainer cache (`~/.apptainer`) and SIF files can fill home directory quota
- **Solution (BMRC)**: Use group scratch space for Apptainer cache
  ```bash
  # Symlink Apptainer cache to group scratch
  mkdir -p /well/kir/scratch/kir-fritzsche/apptainer_cache/$USER
  rm -rf ~/.apptainer  # Remove if exists
  ln -s /well/kir/scratch/kir-fritzsche/apptainer_cache/$USER ~/.apptainer

  # The build script automatically uses scratch for cache and temp files
  bash scripts/build_hpc_image.sh
  ```
- Verify cache symlink: `ls -la ~ | grep apptainer` should show symlink
- The build script automatically handles this when using `/well/kir/scratch/kir-fritzsche`

## Verify Installation

```bash
# Test imports
python -c "import bioio, pyvips, histomicstk, geopandas; print('✓ All dependencies OK')"

# Test workflows
bash python/decon.sh --help
bash python/seg.sh --help
```
