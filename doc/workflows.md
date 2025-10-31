# Workflow Details

Detailed information about color deconvolution and segmentation workflows.

## Interactive Script Features

Both processing scripts (`decon.sh` and `seg.sh`) provide:
- **Input validation**: Automatic checking of file and directory existence
- **Helpful prompts**: Clear descriptions and recommended values
- **Batch processing**: Automatic discovery and processing of multiple samples
- **Progress tracking**: Real-time feedback on processing status
- **Error handling**: Graceful handling of failed samples with summary reporting
- **Configuration summary**: Review settings before processing begins

## Color Deconvolution Workflow

### Overview

The color deconvolution workflow separates PSR and FG stain channels from RGB images using user-defined stain vectors measured in QuPath.

### Running the Workflow

```bash
# Interactive mode
bash python/decon.sh

# Or with pixi
pixi run decon
```

### Configuration Prompts

| Setting | Description | Default | Recommendations |
|---------|-------------|---------|--------------------|
| **Data Directory** | Input directory containing WSI files | Required | Use absolute paths for reliability |
| **Stain Map** | Path to stain vector JSON file | Required | Use QuPath-measured vectors for accuracy |
| **Scaling Factor** | Downsampling for processing | `2` | `2` for large images, `1` for small images |
| **Manual Masks** | Use GeoJSON annotation files | `false` | `true` for precise tissue regions |
| **Batch Size** | Parallel processing batch size | `16` | Increase for more RAM, decrease if memory limited |

### Supported File Formats

**Input formats:**
- `.czi` - Zeiss CZI files
- `.tif`, `.tiff` - Standard TIFF
- `.ome.tif`, `.ome.tiff` - OME-TIFF

**Output files:**
- `color_decon.ome.tiff` - 3-channel deconvolved image (PSR, FG, Residual)
- `PSR.ome.tiff` - PSR channel only with background removal
- `mask.ome.tiff` - Binary tissue mask

### Batch Processing

The script automatically:
- Scans the input directory for all supported image formats
- Processes multiple images sequentially with progress tracking
- Creates individual output directories for each sample
- Handles errors gracefully and provides summary

## Segmentation Workflow

### Overview

The segmentation workflow uses Otsu thresholding to identify collagen-positive regions in PSR-stained images.

### Running the Workflow

```bash
# Interactive mode
bash python/seg.sh

# Or with pixi
pixi run seg
```

### Configuration Prompts

| Setting | Description | Default | Recommendations |
|---------|-------------|---------|--------------------|
| **Processed Data Directory** | Directory with deconvolution results | Required | Should contain subdirectories with PSR files |
| **Tile Size** | Regional analysis tile size (pixels) | `2048` | `2048` for speed, `1024` for detail |
| **Padding** | Tile overlap (pixels) | `0` | `512` for better edge handling |
| **Class ID** | Otsu threshold class selection | `1` | `1` for typical collagen, `2` for dense collagen |

### Output Files

**Image outputs:**
- `collagen.ome.tiff` - Binary collagen segmentation mask

**Data outputs:**
- `res.csv` - Per-tile or whole-image quantification results
  - Columns: `x0`, `y0`, `x1`, `y1`, `collagen (px^2)`, `tissue (px^2)`, `collagen vs tissue (%)`

### Batch Processing

The script automatically:
- Discovers all directories containing `PSR.ome.tiff` files
- Processes each sample directory independently
- Generates individual results and maintains processing statistics
- Provides quick statistics summary for each processed sample

## Advanced Features

### Manual Annotation Support

For precise tissue region definition, you can provide manual annotations:

1. Create annotations in QuPath as region annotations
2. Export as GeoJSON format
3. Place in the same directory as your input image with matching filename
4. Enable with `--manual-mask true` flag

**Benefits:**
- Exclude artifacts or damaged tissue regions
- Focus analysis on specific anatomical structures
- Improve accuracy by removing background

### Automated Batch Processing

For fully automated processing without prompts, you can:

**Option 1: Modify the shell scripts**
Edit `decon.sh` or `seg.sh` to hardcode parameters

**Option 2: Call Python modules directly**
```bash
python -m python.decon \
  --data-dir /path/to/data \
  --stain-map stain_color_map/vectors.json \
  --scaling 2 \
  --batch-size 16

python -m python.seg \
  --data-dir /path/to/processed \
  --tile-size 2048 \
  --padding 0 \
  --class-id 1
```

### Tiled Processing for Large Images

For whole slide images that don't fit in memory:

- Set `--tile-size` to break image into manageable chunks
- Use `--padding` to ensure smooth transitions between tiles
- Results are automatically aggregated across tiles

**Recommendations:**
- Tile size: 2048 for fast processing, 1024 for fine detail
- Padding: 512 pixels provides good overlap for edge handling
- Memory: ~4GB RAM per tile at 2048x2048

## Troubleshooting

### Common Issues

**Issue: Script doesn't find input files**
- Verify file extensions match supported formats
- Check directory paths are absolute, not relative
- Ensure files are not corrupted

**Issue: Out of memory during processing**
- Reduce `--tile-size` (e.g., from 2048 to 1024)
- Decrease `--batch-size` for parallel processing
- Increase `--scaling` factor for downsampling

**Issue: Poor segmentation results**
- Try different `--class-id` values (0, 1, or 2)
- Verify stain vectors are accurate (re-measure in QuPath)
- Check tissue mask quality in `mask.ome.tiff`

**Issue: Processing takes too long**
- Increase `--scaling` factor (2 or 4)
- Use larger `--tile-size` (if memory allows)
- Increase `--batch-size` for parallel processing

## Next Steps

- ⚙️ [Configuration Guide](configuration.md) - Detailed parameter reference
- 📁 [File Formats](file-formats.md) - Input/output specifications
- 🐳 [Docker Guide](docker.md) - Running workflows in containers
