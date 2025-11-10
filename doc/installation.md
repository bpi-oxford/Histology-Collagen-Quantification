# Installation Guide

## Prerequisites

**For all methods:**
- Git with submodule support
- For pyHisto: Access to the Oxford-Zeiss-Centre-of-Excellence/pyHisto repository (SSH key or HTTPS credentials configured)

## Method 1: Docker (Recommended for Production/HPC)

```bash
# Initialize git submodules (required for pyHisto)
git submodule update --init --recursive

# Build image
docker build -t collagen-quant .

# Run
docker run -it --rm -v /path/to/data:/data collagen-quant

# Test
docker run -it --rm collagen-quant bash
python -c "import pyvips, geopandas, bioio, histomicstk"
```

**Note:** The Docker build now uses the pyHisto git submodule from `dependency/pyHisto` instead of requiring a GITHUB_TOKEN build argument.

### Convert to Apptainer/Singularity (HPC)

**Automated Build (Recommended):**

Use the provided build script to automate the entire process:

```bash
# Run the automated build script
bash scripts/build_hpc_image.sh

# This will:
# 1. Check git submodules are initialized
# 2. Build the Docker image
# 3. Save to collagen-quant.tar
# 4. Compress to collagen-quant.tar.gz

# Then transfer to HPC cluster
scp collagen-quant.tar.gz user@cluster:~/archive/images
```

**Manual Build:**

```bash
# On local machine
docker save collagen-quant:latest -o collagen-quant.tar
gzip collagen-quant.tar
scp collagen-quant.tar.gz user@cluster:~/archive/images
```

**On HPC cluster:**

```bash
cd ~/archive/images
gunzip collagen-quant.tar.gz  # Extract tar from tar.gz
apptainer build collagen-quant.sif docker-archive://collagen-quant.tar

# Request SLURM interactive session (adjust resources as needed)
srun -p short --mem=32G --cpus-per-task=8 --time=1-06:00:00 --pty bash

# Interactive mode with bind mounts (access data and config directories)
apptainer shell --bind /path/to/data:/data,/path/to/configs:/app/configs --pwd /app collagen-quant.sif

# Run workflow with proper bind mounts
apptainer exec --bind /path/to/data:/data,/path/to/configs:/app/configs --pwd /app collagen-quant.sif bash python/decon.sh
```

### BMRC Cluster - Automated Script

For Oxford BMRC cluster users, use the provided script for easier job submission:

```bash
# 1. Edit the script configuration
nano scripts/bmrc_apptainer_run.sh

# Configure these variables:
# - SIF_IMAGE: Path to your .sif file (default: ~/images/collagen-quant.sif)
# - DATA_DIR: Your input data directory
# - CONFIG_DIR: Your configs directory
# - WORKFLOW: "decon", "seg", or "both"
# - PARTITION: SLURM queue (short/medium/long)
# - MEM/CPUS/TIME: Resource allocation

# 2. Run from headnode (script handles srun submission)
bash scripts/bmrc_apptainer_run.sh

# The script will automatically run the interactive workflow (decon.sh/seg.sh)
# You'll be able to respond to prompts and see output in real-time
```

**Script features:**
- Validates all paths before submission
- Auto-configures bind mounts for data, configs, and stain maps
- Submits interactive job via `srun --pty` with specified resources
- Runs workflow command directly with `apptainer exec` (allows interactive prompts)
- Supports running deconvolution, segmentation, or both workflows
- Working directory set to `/app` inside container

**Example workflow:**
```bash
# Run deconvolution only
# (edit WORKFLOW="decon" in script)
bash scripts/bmrc_apptainer_run.sh

# Run both workflows sequentially
# (edit WORKFLOW="both" in script)
bash scripts/bmrc_apptainer_run.sh
```

See `scripts/bmrc_apptainer_run.sh` for full configuration options.

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
- Extract first: `gunzip collagen-quant.tar.gz`
- Then build: `apptainer build collagen-quant.sif docker-archive://collagen-quant.tar`

**Cluster home directory quota exceeded:**
- Apptainer cache (`~/.apptainer`) and SIF files can fill home directory quota
- **Solution**: Build SIF files directly in scratch, symlink cache only
  ```bash
  # Symlink Apptainer cache to scratch
  mkdir -p /scratch/$USER/apptainer_cache
  rm -rf ~/.apptainer  # Remove if exists
  ln -s /scratch/$USER/apptainer_cache ~/.apptainer

  # Build SIF directly in scratch (not home directory)
  cd /scratch/$USER/
  apptainer build /scratch/$USER/collagen-quant.sif docker-archive://collagen-quant.tar
  ```
- Verify cache symlink: `ls -la ~ | grep apptainer` should show symlink
- Store all SIF files in `/scratch/$USER/` to avoid quota issues

## Verify Installation

```bash
# Test imports
python -c "import bioio, pyvips, histomicstk, geopandas; print('✓ All dependencies OK')"

# Test workflows
bash python/decon.sh --help
bash python/seg.sh --help
```
