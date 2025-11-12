# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated collagen quantification pipeline for PSR (Picrosirius Red) + FG (Fast Green) stained histology images using color deconvolution and multi-level Otsu thresholding. Designed for whole slide imaging (WSI) with support for CZI, TIFF, and OME-TIFF formats.

## Quick Commands

### Environment Setup

**CRITICAL: Always initialize git submodules first** - The `dependency/pyHisto` submodule is required:
```bash
git submodule update --init --recursive
```

**Pixi (Local development - recommended):**
```bash
pixi install
pixi shell
pip install -e .
pip install -e ./dependency/pyHisto
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

**Conda (Traditional):**
```bash
conda env create -f env.yaml
conda activate collagen_quant
pip install -e .
pip install -e ./dependency/pyHisto
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

**Docker (Production/HPC):**
```bash
docker build -t collagen-quant .
docker run -it --rm -v /path/to/data:/data collagen-quant
```

**BMRC HPC (Apptainer/Singularity):**
```bash
# Method 1: Build from apptainer.def on BMRC (recommended)
# Option A: Using script (easier)
bash scripts/build_hpc_image.sh             # Press Enter for default option 1
# Option B: Direct command
git submodule update --init --recursive
module load Apptainer
apptainer build --fakeroot ~/images/collagen-quant.sif apptainer.def

# Method 2: Build from Docker archive (if you have Docker locally)
bash scripts/build_docker_image.sh          # On local machine
scp collagen-quant.tar.gz user@bmrc:/path/  # Transfer to BMRC
bash scripts/build_hpc_image.sh             # On BMRC, select option 2

# Run workflows
bash scripts/bmrc_apptainer_run.sh          # Interactive workflow selection
```

### Running Workflows

**Interactive mode (recommended for batch processing):**
```bash
bash python/decon.sh     # or: pixi run decon
bash python/seg.sh       # or: pixi run seg
```
These scripts provide guided prompts, auto-discovery of input files, batch processing, and generate reusable TOML configs in `configs/decon/` and `configs/seg/`.

**Direct invocation (single image):**
```bash
python python/decon.py -i input.czi -o output/ -s 2 --stain_map stain_color_map/vectors.json -bn 16
python python/seg.py -i PSR.ome.tiff -o collagen.ome.tiff -m mask.ome.tiff -s res.csv -t 2048 -p 0 -c 1 --classes 4
```

**Jupyter notebooks:**
```bash
pixi run notebook    # Starts JupyterLab on port 8888
```
Main notebook: `notebook/collagen_quantification_mouse.ipynb` contains technical validation and implementation details.

## Architecture

### Pipeline Overview
Two-stage pipeline with independent modules connected by file I/O:
```
Input WSI → [decon.py] → PSR.ome.tiff + mask.ome.tiff → [seg.py] → collagen.ome.tiff + res.csv
```

### Core Processing Modules (`python/`)

**`decon.py`** - Color deconvolution (Stage 1)
- **Input**: WSI files (CZI/TIFF/OME-TIFF) via `bioio`/`aicsimageio`
- **Processing**:
  - Parallel batch processing (`--batch_num`, default 16)
  - Applies HistomicsTK color deconvolution with QuPath-compatible stain vectors
  - Optional manual GeoJSON mask support (`--mask`)
  - Downsampling via `--scaling` factor
- **Output**:
  - `color_decon.ome.tiff` (3-channel pyramidal: PSR, FG, Residual)
  - `PSR.ome.tiff` (single channel, background-removed)
  - `mask.ome.tiff` (binary tissue mask)
- **Key function**: Tiled processing for memory-efficient handling of large WSI

**`seg.py`** - Collagen segmentation (Stage 2)
- **Input**: `PSR.ome.tiff` and `mask.ome.tiff` from decon.py
- **Processing**:
  - Multi-level Otsu thresholding (`--classes`, default 4)
  - Class selection (`-c`/`--class`, typically 1 for collagen)
  - Tiled regional analysis with overlap (`--tile_size`, `--padding`)
- **Output**:
  - `collagen.ome.tiff` (binary segmentation mask)
  - `res.csv` (per-tile quantification: collagen area, tissue area, percentage)
- **Key function**: `iterate_over_regions()` handles tile iteration with configurable overlap

**`decon.sh` / `seg.sh`** - Interactive wrappers
- User-friendly prompts with validation
- Auto-discovery and batch processing of multiple samples
- Generate/load TOML configs in `configs/decon/` and `configs/seg/`
- Progress tracking and error reporting

**`vips_path_windows.py`** - Windows compatibility
- Must be imported before `pyvips` on Windows
- Auto-configures libvips PATH from `.vips_config.ini` or common locations

### Key Dependencies

**Critical installation order** (especially in Docker):
1. **Java JDK** - Required by `histomicstk` (via python-javabridge)
2. **histomicstk** - Must install FIRST before pyHisto:
   ```bash
   python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
   ```
3. **pyHisto** - Install from git submodule (`dependency/pyHisto/`) in editable mode with `--no-deps`:
   ```bash
   pip install --no-deps -e ./dependency/pyHisto
   ```

**Dependency categories**:
- **Image I/O**: `bioio` (with plugins: `bioio-czi`, `bioio-ome-tiff`, `bioio-tifffile`), `pyvips`, `tifffile`
- **Processing**: `histomicstk` (color deconvolution), `scikit-image` (Otsu thresholding), `numpy`, `scipy`
- **Geospatial**: `geopandas`, `rasterio`, `gdal` (for GeoJSON mask support)
- **Private**: `pyHisto` (provides utilities for I/O and deconvolution, installed from git submodule)

### Configuration Files

**Stain vectors** (`stain_color_map/*.json`):
- QuPath-compatible RGB color deconvolution vectors
- MUST be measured from your specific staining batch in QuPath
- Format: `{"PSR": [R, G, B], "FG": [R, G, B], "Residual": [R, G, B]}`
- Values are normalized vectors (magnitude ~1.0)

**Workflow configs** (`configs/decon/*.toml`, `configs/seg/*.toml`):
- Auto-generated by interactive shell scripts
- Reusable for batch processing with consistent parameters
- Store paths, processing parameters, and metadata

## Platform-Specific Considerations

**Windows**:
- Requires libvips installed separately (run `setup_windows.sh`)
- MUST import `vips_path_windows` before `pyvips` in Python scripts
- Configuration stored in `.vips_config.ini`

**HPC/BMRC**:
- Use Apptainer/Singularity with `--platform=linux/amd64`
- Build scripts support development mode (mount local code over container)
- Temp files use `/well/kir/scratch/` or home directory

**macOS/Linux (local)**:
- Pixi automatically installs libvips via conda
- No special configuration needed

## Critical Processing Parameters

**Memory management**:
- `--tile_size` (default 2048px) - Larger = faster but more RAM
- `--scaling` (default 1-2) - Downsampling for processing
- `--batch_num` (default 16) - Parallel batch size for deconvolution

**Stain separation**:
- Stain vectors must be measured from your specific images in QuPath
- Wrong vectors = incorrect collagen quantification
- Store multiple vector sets for different staining batches

**Segmentation**:
- `--classes` (default 4) - Number of Otsu threshold levels
- `--class`/`-c` (typically 1) - Which threshold class represents collagen
- `--padding` (0-512px) - Tile overlap to prevent edge artifacts
  - 0 = no overlap (faster, regional analysis)
  - 512 = significant overlap (smoother boundaries, slower)

## Development Workflow

**Adding new features**:
1. Test locally with Pixi environment
2. Update `python/` source files
3. Test in Docker/Apptainer for HPC compatibility
4. Update documentation in `doc/` if adding user-facing features

**Testing on BMRC without rebuilding**:
```bash
bash scripts/bmrc_apptainer_run.sh
# Select development mode (y)
# Provide path to local python/ directory
# Container will use local code instead of built-in version
```

**Common modification patterns**:
- New stain types: Update `decon.py` to handle additional channels
- New segmentation methods: Modify `seg.py` threshold logic
- New file formats: Add `bioio` plugins to dependencies
- Windows compatibility: Update `vips_path_windows.py` with new paths

## Testing

**Manual testing**:
- Test WSI loading: `python python/test_czi_loading.py`
- Debug deconvolution: `bash python/debug_decon.sh`
- Test specific CZI files: `bash python/test_czi.sh`

**pyHisto tests** (in submodule):
- Location: `dependency/pyHisto/tests/`
- Run with: `pytest dependency/pyHisto/tests/`

## Troubleshooting

**"libvips not found" on Windows**:
- Run `bash setup_windows.sh` to install/configure libvips
- Check `.vips_config.ini` has correct path

**"histomicstk import error"**:
- Ensure Java JDK is installed
- Use special wheel: `python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels`

**"pyHisto not found"**:
- Run `git submodule update --init --recursive`
- Install in editable mode: `pip install -e ./dependency/pyHisto`

**Out of memory during processing**:
- Increase `--scaling` (downsample more)
- Decrease `--tile_size`
- Decrease `--batch_num`

## Documentation Reference

- `README.MD` - Quick start guide
- `doc/quickstart.md` - Step-by-step tutorial with screenshots
- `doc/installation.md` - Platform-specific setup (Windows/macOS/Linux/HPC)
- `doc/workflows.md` - Parameter explanations and troubleshooting
- `doc/file-formats.md` - Input/output file specifications
- `doc/docker.md` - Container deployment and BMRC setup
- `notebook/collagen_quantification_mouse.ipynb` - Technical validation and implementation details
