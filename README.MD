# Histology Collagen Quantification

Automated collagen quantification pipeline for PSR (Picrosirius Red) + FG (Fast Green) stained whole slide images.

## Features

- Multi-format support: CZI, TIFF, OME-TIFF
- QuPath-compatible color deconvolution
- Multi-level Otsu thresholding
- Tiled processing for large WSI
- Docker & Apptainer/Singularity support

## Quick Start

### Installation

**Docker (Production/HPC):**
```bash
export GITHUB_TOKEN=ghp_your_token_here
docker build --build-arg GITHUB_TOKEN -t collagen-quant .
docker run -it --rm -v /path/to/data:/data collagen-quant
```

**Pixi (Fast local setup):**
```bash
pixi install && pixi shell
pip install -e .
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

**Conda:**
```bash
conda env create -f env.yaml && conda activate collagen_quant
pip install -e .
python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels
```

> **Note:** GitHub Personal Access Token with `repo` scope required. See [Installation Guide](doc/installation.md) for details.

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

## Output Files

- `color_decon.ome.tiff` - Deconvolved channels
- `PSR.ome.tiff` - PSR channel only
- `collagen.ome.tiff` - Binary segmentation mask
- `res.csv` - Quantification statistics (x0, y0, x1, y1, collagen_px, tissue_px, collagen_%)

## License

MIT License - see [LICENSE](LICENSE) for details
