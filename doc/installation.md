# Installation Guide

## Prerequisites

**For all methods:**
- GitHub Personal Access Token with `repo` scope ([create here](https://github.com/settings/tokens))

## Method 1: Docker (Recommended for Production/HPC)

```bash
# Build image
export GITHUB_TOKEN=ghp_your_token_here
docker build --build-arg GITHUB_TOKEN -t collagen-quant .

# Run
docker run -it --rm -v /path/to/data:/data collagen-quant

# Test
docker run -it --rm collagen-quant bash
python -c "import pyvips, geopandas, bioio, histomicstk"
```

### Convert to Apptainer/Singularity (HPC)

```bash
# On local machine
docker save collagen-quant:latest -o collagen-quant.tar
gzip collagen-quant.tar
scp collagen-quant.tar.gz user@cluster:/scratch/$USER/

# On HPC cluster
cd /scratch/$USER/
gunzip collagen-quant.tar.gz  # Extract tar from tar.gz
apptainer build collagen-quant.sif docker-archive://collagen-quant.tar

# Run on HPC
apptainer exec collagen-quant.sif bash python/decon.sh
```

## Method 2: Pixi (Fastest for Local Development)

```bash
# Install pixi (if needed)
curl -fsSL https://pixi.sh/install.sh | bash

# Setup environment
pixi install
pixi shell
pip install -e .
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

## Method 3: Conda (Traditional)

```bash
# Create environment
conda env create -f env.yaml
conda activate collagen_quant

# Install package
pip install -e .
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

## Platform-Specific Notes

### Windows
- Requires libvips: run `bash setup_windows.sh` first
- WSL2 recommended for better performance

### macOS/Linux
- libvips installed automatically via conda
- Pixi is fastest setup method

## Troubleshooting

**"GITHUB_TOKEN not set" error:**
```bash
# Create token: https://github.com/settings/tokens (select 'repo' scope)
export GITHUB_TOKEN=ghp_your_token_here
```

**Docker build fails with GPG errors:**
```bash
docker system prune -f
docker build --no-cache --build-arg GITHUB_TOKEN -t collagen-quant .
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

## Verify Installation

```bash
# Test imports
python -c "import bioio, pyvips, histomicstk, geopandas; print('✓ All dependencies OK')"

# Test workflows
bash python/decon.sh --help
bash python/seg.sh --help
```
