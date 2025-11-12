# Histology Collagen Quantification

Automated collagen quantification pipeline for PSR (Picrosirius Red) + FG (Fast Green) stained whole slide images.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Installation](#installation)
  - [Basic Usage](#basic-usage)
- [Documentation](#documentation)
- [Setup Instructions](#setup-instructions)
  - [Windows Setup](#windows-setup)
  - [Local Development Setup](#local-development-setup)
  - [HPC/Cluster Setup](#cluster-install)
  - [BMRC Cluster - Apptainer Build](#bmrc-cluster---apptainer-build)
- [Workflow Steps](#workflow-steps)
  - [1. Stain Vector Measurement](#2-stain-vector-measurement-in-qupath)
  - [2. Color Deconvolution](#3-color-deconvolution)
  - [3. Collagen Segmentation](#4-collagen-segmentation)
- [Configuration](#script-configuration-options)
- [File Structure](#inputoutput-file-structure)
- [Advanced Features](#advanced-features)
- [Technical Details](#technical-details)

## Features

- Multi-format support: CZI, TIFF, OME-TIFF
- QuPath-compatible color deconvolution
- Multi-level Otsu thresholding
- Tiled processing for large WSI
- Docker & Apptainer/Singularity support
- Development mode for live code editing in containers

## Quick Start

### Installation

**First-time setup - Clone with submodules:**
```bash
# New clone
git clone --recursive <repository-url>

# Existing clone - initialize submodules
git submodule update --init --recursive
```

**Docker (Production/HPC):**
```bash
git submodule update --init --recursive
docker build -t collagen-quant .
docker run -it --rm -v /path/to/data:/data collagen-quant
```

**Pixi (Fast local setup):**
```bash
git submodule update --init --recursive
pixi install && pixi shell
pip install -e .
pip install -e ./dependency/pyHisto
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

**Conda:**
```bash
git submodule update --init --recursive
conda env create -f env.yaml && conda activate collagen_quant
pip install -e .
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

> **Note:** pyHisto is included as a git submodule in `dependency/pyHisto`. See [Installation Guide](doc/installation.md) for details.

### Basic Usage

```bash
# 1. Measure stain vectors in QuPath
# 2. Run color deconvolution
bash python/decon.sh     # or: pixi run decon
# 3. Run segmentation
bash python/seg.sh       # or: pixi run seg
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Quick Start](doc/quickstart.md) | Step-by-step tutorial |
| [Installation](doc/installation.md) | Platform-specific setup |
| [Workflows](doc/workflows.md) | Parameters and troubleshooting |
| [File Formats](doc/file-formats.md) | Input/output specifications |
| [Docker Guide](doc/docker.md) | Container usage and HPC |

## Setup Instructions

### Windows Setup

Run in Git Bash - will prompt for installation directory:
```bash
bash setup_windows.sh
```

### Local Development Setup

Use Pixi (recommended for fastest setup) or Conda. See [Installation Guide](doc/installation.md) for detailed instructions.

### Cluster Install

On cluster environments, pyHisto is automatically handled via git submodules. Ensure submodules are initialized before building:
```bash
git submodule update --init --recursive
```

For Docker/Apptainer deployment, see the BMRC section below and the [Installation Guide](doc/installation.md).

### BMRC Cluster - Apptainer Build

For Oxford BMRC cluster users, there are two build options:

**Option 1: Build from apptainer.def on BMRC (Recommended)**
```bash
# On BMRC cluster - Method A: Using interactive script (easier)
bash scripts/build_hpc_image.sh
# Press Enter to select default option 1 (apptainer.def)

# Or Method B: Direct command
module load Apptainer
git submodule update --init --recursive
cd /gpfs3/well/kir-fritzsche/projects/Histology-Collagen-Quantification
apptainer build --fakeroot ~/images/collagen-quant.sif apptainer.def
```

**Option 2: From Docker Archive**
```bash
# On local machine (with Docker installed)
bash scripts/build_docker_image.sh

# Transfer to BMRC
scp collagen-quant.tar.gz user@bmrc:/users/kir-fritzsche/oyk357/archive/images/

# On BMRC cluster - Build SIF from archive
bash scripts/build_hpc_image.sh
# Select option 2 (uses default path: /users/kir-fritzsche/oyk357/archive/images/collagen-quant.tar.gz)
```

**Running the Workflow:**
```bash
# Interactive workflow with prompts
bash scripts/bmrc_apptainer_run.sh
# Select workflow (decon/seg/both/debug/pytest-czi)
# Enable development mode to override container code (optional)
```

**Note:** The script uses `/well/kir/scratch/kir-fritzsche/` for temporary build files. If you don't have access, the script will prompt to use home directory instead.

See [BMRC Installation Guide](doc/installation.md#bmrc-cluster-build) for detailed configuration options.

## Workflow Steps

### 1. Stain Vector Measurement in QuPath

1. Open your PSR+FG stained image in QuPath
2. Go to `Analyze` → `Preprocessing` → `Estimate stain vectors`
3. Select representative tissue regions with clear PSR and FG staining
4. Export the measured stain vectors to a JSON file in the `stain_color_map/` directory

**Example stain vector format:**
```json
{
    "PSR": [0.193, 0.75, 0.632],
    "FG": [0.718, 0.163, 0.677],
    "Residual": [-0.912, -0.281, 0.298]
}
```

### 2. Color Deconvolution

Run the interactive color deconvolution script to separate stain channels:

```bash
# Start the interactive script
bash python/decon.sh
```

The script will guide you through the following prompts:
1. **Data directory**: Path to your input WSI files
2. **Stain color map**: Select from available JSON files in `stain_color_map/`
3. **Scaling factor**: Downsampling level (recommended: 2 for large images)
4. **Manual masks**: Whether to use GeoJSON annotation files
5. **Batch size**: Number of parallel processes (recommended: 16)

The script will automatically:
- Scan for supported image formats (CZI, TIFF, OME-TIFF)
- Create output directories for each image
- Process all images in batch
- Provide progress feedback and error handling

### 3. Collagen Segmentation

Run the interactive segmentation script to quantify collagen:

```bash
# Start the interactive script
bash python/seg.sh
```

The script will guide you through the following prompts:
1. **Processed data directory**: Path containing deconvolution results
2. **Tile size**: Regional analysis tile size in pixels (recommended: 2048)
3. **Padding**: Overlap between tiles in pixels (recommended: 0-512)
4. **Class ID**: Otsu threshold class for collagen (recommended: 1)

The script will automatically:
- Validate that required PSR.ome.tiff files exist
- Process all directories containing deconvolution results
- Generate collagen segmentation masks and quantification statistics
- Display quick statistics after processing each sample
```

## Interactive Script Features

Both processing scripts (`decon.sh` and `seg.sh`) provide:
- **Input validation**: Automatic checking of file and directory existence
- **Helpful prompts**: Clear descriptions and recommended values
- **Batch processing**: Automatic discovery and processing of multiple samples
- **Progress tracking**: Real-time feedback on processing status
- **Error handling**: Graceful handling of failed samples with summary reporting
- **Configuration summary**: Review settings before processing begins
```

## Script Configuration Options

### Color Deconvolution Settings

| Setting | Description | Default | Recommendations |
|---------|-------------|---------|-----------------|
| **Data Directory** | Input directory containing WSI files | Required | Use absolute paths for reliability |
| **Stain Map** | Path to stain vector JSON file | Required | Use QuPath-measured vectors for accuracy |
| **Scaling Factor** | Downsampling for processing | `2` | `2` for large images, `1` for small images |
| **Manual Masks** | Use GeoJSON annotation files | `false` | `true` for precise tissue regions |
| **Batch Size** | Parallel processing batch size | `16` | Increase for more RAM, decrease if memory limited |

### Segmentation Settings

| Setting | Description | Default | Recommendations |
|---------|-------------|---------|-----------------|
| **Processed Data Directory** | Directory with deconvolution results | Required | Should contain subdirectories with PSR files |
| **Tile Size** | Regional analysis tile size (pixels) | `2048` | `2048` for speed, `1024` for detail |
| **Padding** | Tile overlap (pixels) | `0` | `512` for better edge handling |
| **Class ID** | Otsu threshold class selection | `1` | `1` for typical collagen, `2` for dense collagen |

## Input/Output File Structure

### Input Structure
```
project_root/
├── raw_images/
│   ├── sample_01.czi
│   ├── sample_02.czi
│   └── sample_03.czi
├── stain_color_map/
│   └── psr_fg_vectors.json
└── manual_masks/ (optional)
    ├── sample_01.geojson
    └── sample_02.geojson
```

### Output Structure
```
processed_data/
├── sample_01/
│   ├── color_decon.ome.tiff    # 3-channel deconvolved image
│   ├── PSR.ome.tiff            # PSR channel only
│   ├── mask.ome.tiff           # Tissue mask
│   ├── collagen.ome.tiff       # Collagen segmentation
│   └── res.csv                 # Quantification results
├── sample_02/
│   └── ... (same structure)
└── summary_statistics.csv
```

### Output File Descriptions

#### Images
- **`color_decon.ome.tiff`**: 3-channel pyramidal OME-TIFF containing PSR, FG, and residual channels
- **`PSR.ome.tiff`**: Single-channel PSR signal with background removal applied
- **`mask.ome.tiff`**: Binary tissue mask used for analysis region definition
- **`collagen.ome.tiff`**: Binary collagen segmentation mask

#### Data Files
- **`res.csv`**: Per-tile or whole-image quantification results
  - Columns: `x0`, `y0`, `x1`, `y1`, `collagen (px^2)`, `tissue (px^2)`, `collagen vs tissue (%)`

## Advanced Features

### Manual Annotation Support

For precise tissue region definition, you can provide manual annotations:

1. Create annotations in QuPath as region annotations
2. Export as GeoJSON format
3. Place in the same directory as your input image with matching filename
4. Enable with `--manual-mask true` flag

### Automated Batch Processing

Both interactive scripts automatically handle batch processing:

**Color Deconvolution (`decon.sh`)**:
- Scans the input directory for all supported image formats
- Processes multiple images sequentially with progress tracking
- Creates individual output directories for each sample
- Supported formats: `.czi`, `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`

**Segmentation (`seg.sh`)**:
- Automatically discovers all directories containing PSR.ome.tiff files
- Processes each sample directory independently
- Generates individual results and maintains processing statistics
- Provides quick statistics summary for each processed sample

For fully automated processing without prompts, you can modify the scripts or call the underlying Python modules directly with command-line arguments.

### Development Mode (Container Code Override)

For BMRC Apptainer users, development mode allows testing code changes without rebuilding the container image:

**Interactive prompt (recommended):**
```bash
bash scripts/bmrc_apptainer_run.sh
# Answer "y" when prompted for development mode
# Provide path to local Python source directory
```

**How it works:**
- Mounts local `python/` directory over container's `/app/python`
- Changes to Python code are immediately reflected in container
- Useful for debugging, testing fixes, and rapid iteration
- No need to rebuild SIF image for each code change

**Use cases:**
- Testing bug fixes before committing
- Experimenting with parameter changes
- Debugging pipeline issues with diagnostic prints
- Developing new features

See `scripts/bmrc_apptainer_run.sh` for configuration details.

<!-- ## Citation

If you use this pipeline in your research, please cite:
```
[Your publication details here]
``` -->

## Technical Details

For detailed technical implementation and validation, see the Jupyter [notebook](./notebook/collagen_quantification_mouse.ipynb).
