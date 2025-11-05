# File Formats and Directory Structure

Complete guide to input/output file formats and directory organization.

## Input File Structure

### Recommended Directory Layout

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

### Supported Input Formats

#### Image Files

| Format | Extension | Description | Best For |
|--------|-----------|-------------|----------|
| **CZI** | `.czi` | Zeiss proprietary format | Zeiss microscope outputs |
| **TIFF** | `.tif`, `.tiff` | Standard TIFF | General purpose |
| **OME-TIFF** | `.ome.tif`, `.ome.tiff` | Open Microscopy Environment TIFF | Multi-channel, metadata-rich images |

**Requirements:**
- RGB or multi-channel images
- Minimum recommended resolution: 0.5 µm/pixel
- File size: No hard limit (tiled processing handles large files)

#### Stain Vector Files

**Format:** JSON

**Location:** `stain_color_map/` directory

**Structure:**
```json
{
    "PSR": [0.193, 0.75, 0.632],
    "FG": [0.718, 0.163, 0.677],
    "Residual": [-0.912, -0.281, 0.298]
}
```

**How to generate:**
1. Open image in QuPath
2. Go to `Analyze` → `Preprocessing` → `Estimate stain vectors`
3. Select representative tissue regions
4. Export to JSON

#### Manual Annotation Files (Optional)

**Format:** GeoJSON

**Location:** Same directory as input image, matching filename

**Example:**
- Image: `raw_images/sample_01.czi`
- Annotation: `raw_images/sample_01.geojson`

**How to generate:**
1. Create region annotations in QuPath
2. Export as GeoJSON format

## Output File Structure

### Directory Organization

```
processed_data/
├── sample_01/
│   ├── color_decon.ome.tiff    # 3-channel deconvolved image
│   ├── PSR.ome.tiff             # PSR channel only
│   ├── mask.ome.tiff            # Tissue mask
│   ├── collagen.ome.tiff        # Collagen segmentation
│   └── res.csv                  # Quantification results
├── sample_02/
│   └── ... (same structure)
└── summary_statistics.csv       # Aggregated results (optional)
```

### Output File Descriptions

#### Image Outputs

##### 1. `color_decon.ome.tiff`

**Description:** 3-channel pyramidal OME-TIFF containing deconvolved stain channels

**Channels:**
- Channel 0: PSR (Picrosirius Red)
- Channel 1: FG (Fast Green)
- Channel 2: Residual (background/artifacts)

**Properties:**
- Format: Pyramidal OME-TIFF (multi-resolution)
- Bit depth: 32-bit float
- Dimensions: Same as input image
- Metadata: Full OME-XML metadata preserved

**Use cases:**
- Visual inspection of deconvolution quality
- QuPath import for further analysis
- Publication figures

---

##### 2. `PSR.ome.tiff`

**Description:** Single-channel PSR signal with background removal applied

**Properties:**
- Format: Pyramidal OME-TIFF
- Bit depth: 32-bit float
- Processing: Background subtraction and normalization
- Dimensions: Same as input image

**Use cases:**
- Input for segmentation workflow
- Quantitative intensity analysis
- Direct collagen visualization

---

##### 3. `mask.ome.tiff`

**Description:** Binary tissue mask used for analysis region definition

**Properties:**
- Format: OME-TIFF
- Bit depth: 8-bit (0=background, 255=tissue)
- Method: Multi-level Otsu thresholding + morphological operations
- Dimensions: Same as input image

**Use cases:**
- Define regions for quantification
- Exclude background and artifacts
- QC for tissue detection

---

##### 4. `collagen.ome.tiff`

**Description:** Binary collagen segmentation mask

**Properties:**
- Format: OME-TIFF
- Bit depth: 8-bit (0=non-collagen, 255=collagen)
- Method: Otsu thresholding on PSR channel
- Dimensions: Same as input image

**Use cases:**
- Final collagen distribution visualization
- Overlay with original image
- Export for GIS/spatial analysis

#### Data Outputs

##### `res.csv`

**Description:** Per-tile or whole-image quantification results

**Columns:**

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `x0` | int | pixels | Top-left X coordinate of tile |
| `y0` | int | pixels | Top-left Y coordinate of tile |
| `x1` | int | pixels | Bottom-right X coordinate of tile |
| `y1` | int | pixels | Bottom-right Y coordinate of tile |
| `collagen (px^2)` | float | pixels² | Total collagen area |
| `tissue (px^2)` | float | pixels² | Total tissue area |
| `collagen vs tissue (%)` | float | % | Collagen percentage |

**Example:**
```csv
x0,y0,x1,y1,collagen (px^2),tissue (px^2),collagen vs tissue (%)
0,0,2048,2048,145632.0,3894521.0,3.74
2048,0,4096,2048,189234.0,3912456.0,4.84
```

**Notes:**
- For whole-image analysis: single row with full image coordinates
- For tiled analysis: multiple rows, one per tile
- Pixels can be converted to physical units using image metadata

##### `summary_statistics.csv` (Optional)

**Description:** Aggregated results across all samples

**Columns:**
- Sample ID
- Total tissue area
- Total collagen area
- Collagen percentage
- Mean intensity
- Standard deviation
- Additional statistics as configured

## File Size Considerations

### Typical File Sizes

| File Type | Compression | Size (20K×20K image) | Notes |
|-----------|-------------|----------------------|-------|
| Input CZI | Native | 500 MB - 2 GB | Varies by compression |
| color_decon.ome.tiff | LZW | 300 MB - 1 GB | 3 channels, pyramidal |
| PSR.ome.tiff | LZW | 100 MB - 400 MB | 1 channel, pyramidal |
| mask.ome.tiff | LZW | 10 MB - 50 MB | Binary, compressed well |
| collagen.ome.tiff | LZW | 10 MB - 50 MB | Binary, compressed well |
| res.csv | None | < 1 MB | Text format |

### Storage Recommendations

**Per sample (complete workflow):**
- Raw image: ~1 GB
- Processed outputs: ~500 MB - 1.5 GB
- **Total: ~1.5 - 2.5 GB per sample**

**For batch processing:**
- 10 samples: ~15-25 GB
- 100 samples: ~150-250 GB
- Consider using scratch/temporary storage on HPC

## Data Import/Export

### Importing to QuPath

```groovy
// Import deconvolved image
def deconPath = "/path/to/sample_01/color_decon.ome.tiff"
def server = new OpenslideServerBuilder().buildServer(deconPath)
def viewer = qupath.getViewer()
viewer.setImageData(new ImageData<>(server))

// Import collagen mask as annotation
def maskPath = "/path/to/sample_01/collagen.ome.tiff"
// ... (QuPath script to import mask)
```

### Exporting for Analysis

**Python (pandas):**
```python
import pandas as pd

# Read quantification results
df = pd.read_csv("sample_01/res.csv")

# Calculate summary statistics
mean_collagen = df["collagen vs tissue (%)"].mean()
std_collagen = df["collagen vs tissue (%)"].std()

print(f"Mean collagen: {mean_collagen:.2f}%")
print(f"Std deviation: {std_collagen:.2f}%")
```

**R:**
```r
# Read quantification results
df <- read.csv("sample_01/res.csv")

# Calculate summary statistics
mean_collagen <- mean(df$collagen.vs.tissue....)
sd_collagen <- sd(df$collagen.vs.tissue....)

cat(sprintf("Mean collagen: %.2f%%\n", mean_collagen))
cat(sprintf("Std deviation: %.2f%%\n", sd_collagen))
```

## Metadata Standards

### OME-TIFF Metadata

All output OME-TIFF files include:
- Physical pixel sizes (µm)
- Channel names and colors
- Acquisition parameters (if available from input)
- Processing timestamps
- Software version information

**Accessing metadata:**
```python
from ome_types import from_tiff

# Read OME metadata
metadata = from_tiff("color_decon.ome.tiff")
print(metadata.images[0].pixels.physical_size_x)
```

## Next Steps

- 📖 [Workflow Guide](workflows.md) - Detailed workflow documentation
- ⚙️ [Configuration Guide](configuration.md) - Parameter settings
- 🐳 [Docker Guide](docker.md) - Container usage
