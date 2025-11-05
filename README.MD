# Histology Collagen Quantification

High resolution histology slice scanning quantification with PSR (Picrosirius Red) + FG (Fast Green) staining for automated collagen detection and quantification.

## Overview

This pipeline provides automated analysis of histological images stained with PSR+FG to quantify collagen content in tissue samples. The workflow combines color deconvolution techniques with advanced segmentation algorithms to provide accurate, reproducible measurements suitable for research applications.

## Pipeline Features

1. **Multi-format image support**: CZI, TIFF, OME-TIFF file formats
2. **Color deconvolution**: User-defined stain vectors compatible with QuPath measurements
3. **Automated tissue detection**: Multi-level Otsu thresholding with morphological operations
4. **Scalable processing**: Tiled processing for large whole slide images
5. **Quantitative analysis**: Regional and global collagen density measurements
6. **Output formats**: Pyramidal OME-TIFF for visualization and CSV for statistical analysis

## Workflow Overview

```mermaid
flowchart TD
    A[Raw WSI Images<br/>CZI/TIFF] --> B[QuPath Stain Vector<br/>Measurement]
    B --> C[Color Deconvolution<br/>python/decon.sh]
    C --> D[PSR Channel<br/>Extraction]
    C --> E[Tissue Mask<br/>Generation]
    D --> F[Collagen Segmentation<br/>python/seg.sh]
    E --> F
    F --> G[Quantitative Results<br/>CSV Statistics]
    F --> H[Segmentation Masks<br/>OME-TIFF]
```

## Quick Start

### 1. Environment Setup

```bash
# Create environment from env.yaml
mamba env create -f env.yaml

# Activate environment
mamba activate collagen_quant

# Platform-Specific Dependencies

## macOS
brew install vips

## Ubuntu/Debian
sudo apt-get install libvips-dev libgdal-dev default-jre

## Windows
# Run in Git Bash - will prompt for installation directory
bash setup_windows.sh
```

#### Notes for Windows Installation
The `setup_windows.sh` script automatically:
- Downloads and installs libvips 8.16.0
- Saves installation path to `.vips_config.ini`
- Configures Python scripts to use the correct path
- Optionally creates conda environment

**Manual Installation:** Download from [libvips.org/install.html](https://www.libvips.org/install.html), extract, and update `.vips_config.ini`:
```ini
[libvips]
install_dir = C:\your\path\to\vips-dev-8.16.0
```

#### Run in Git Bash - will prompt for installation directory
```bash
bash setup_windows.sh
```

#### Cluster Install
On cluster environment often some dependency packages are not able to install via `sudo`, in particular `histomicstk`. It is recommneded to do manual `pyHisto` install and histomicstk installation 
<!-- TODO: make code to automatically pull pyhisto, comment out the histomicstk and pyHisto in both repo, and do the dep install -->

### 2. Stain Vector Measurement in QuPath

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

### 3. Color Deconvolution

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

### 4. Collagen Segmentation

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

<!-- ## Citation

If you use this pipeline in your research, please cite:
```
[Your publication details here]
``` -->

## Technical Details

For detailed technical implementation and validation, see the Jupyter [notebook](./notebook/collagen_quantification_mouse.ipynb).