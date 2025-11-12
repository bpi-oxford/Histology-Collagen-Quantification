# Quick Start: Tile Loading Optimization

**TL;DR**: Your tile loading is I/O-bound (96.3% time in disk reads). Threading doesn't help (only 1.4% speedup). You can get **3-5x faster** with simple changes.

---

## 🚀 Quick Wins (Do These First)

### 1. Test Downsampling (2 minutes)

**Easiest way to get 2-4x speedup** - just use the existing `--scaling` parameter:

```bash
# Run with 1/2 resolution (4x fewer tiles)
bash python/decon.sh
# When prompted:
#   - Scaling factor: 2
#   - Keep other defaults

# Or direct command:
python python/decon.py -i input.czi -o output/ --scaling 2
```

**Check**: Does the output quality meet your analysis needs?
- If YES → use this for all processing (instant 2-3x speedup)
- If NO → try Strategy 2 below

---

### 2. Visualize Your Tile Pattern (5 minutes)

Understand if spatial sorting will help:

```bash
# On BMRC with development mode enabled
python benchmark/visualize_tile_pattern.py \
    /path/to/your/file.czi \
    -o results/tile_pattern.png

# Download and view tile_pattern.png
```

This shows:
- How tiles are arranged in your CZI file
- Expected improvement from spatial sorting
- Optimal reading order

---

### 3. Apply Spatial Sorting Optimization (10 minutes)

**Expected: 20-40% speedup with NO trade-offs**

Edit `dependency/pyHisto/pyHisto/io.py` around line 219:

```python
# Find this line:
tile_items = [(idx, tile_bboxes[idx]) for idx in tile_indices]

# Add these lines right after:
tile_items_sorted = sorted(tile_items, key=lambda t: (t[1]["y"], t[1]["x"]))
print(f"Tiles will be read in spatial order (Y then X) to minimize disk seeks...")
tile_items = tile_items_sorted
```

Or apply the patch:
```bash
cd /gpfs3/well/kir-fritzsche/projects/Histology-Collagen-Quantification
patch -p1 < patches/optimize_tile_loading.patch
```

**Test it**:
```bash
bash scripts/bmrc_apptainer_run.sh
# Select:
#   - Development mode: y
#   - Python source: /users/kir-fritzsche/oyk357/projects/Histology-Collagen-Quantification/python
#   - Workflow: benchmark-czi

# Compare results/benchmark/benchmark_results_*.json files
```

---

## 📊 How to Measure Improvement

### Before Optimization (Baseline)

```bash
# Run benchmark with current code
python benchmark/benchmark_czi_loading.py \
    /path/to/file.czi \
    --max-tiles 100 \
    --quick \
    --output results/baseline.json

# Note the "Sequential" time (e.g., 95.64s)
```

### After Optimization

```bash
# Apply changes, then re-run
python benchmark/benchmark_czi_loading.py \
    /path/to/file.czi \
    --max-tiles 100 \
    --quick \
    --output results/optimized.json

# Compare times
```

### Calculate Speedup

```python
import json

baseline = json.load(open('results/baseline.json'))
optimized = json.load(open('results/optimized.json'))

baseline_time = baseline[0]['elapsed_seconds']
optimized_time = optimized[0]['elapsed_seconds']

speedup = baseline_time / optimized_time
improvement = (1 - optimized_time / baseline_time) * 100

print(f"Speedup: {speedup:.2f}x")
print(f"Improvement: {improvement:.1f}% faster")
print(f"Time saved per image: {baseline_time - optimized_time:.1f} seconds")
```

---

## 🎯 Expected Results

Based on your profiling data:

| Optimization | Complexity | Expected Time | Speedup | Quality Impact |
|--------------|-----------|---------------|---------|----------------|
| **Baseline** | - | 95s | 1.0x | - |
| **Spatial Sorting** | Low | 60-75s | 1.3-1.6x | None |
| **Downsampling (--scaling 2)** | None | 30-40s | 2.4-3.2x | Lower resolution |
| **Both Combined** | Low | 20-25s | 3.8-4.8x | Lower resolution |

For full image (723 tiles):
- **Baseline**: ~9.2 minutes
- **With spatial sorting**: ~6 minutes
- **With scaling=2**: ~2.5 minutes
- **Both**: ~1.5 minutes

---

## 🔧 Troubleshooting

### "Patch failed to apply"

Manually edit `dependency/pyHisto/pyHisto/io.py`:

1. Open in editor
2. Go to line 219 (search for `tile_items = [(idx, tile_bboxes[idx])`)
3. Add these 3 lines right after:
   ```python
   tile_items_sorted = sorted(tile_items, key=lambda t: (t[1]["y"], t[1]["x"]))
   print(f"Tiles will be read in spatial order...")
   tile_items = tile_items_sorted
   ```
4. Save

### "Development mode not working"

Ensure you're mounting the correct directory:
```bash
# In bmrc_apptainer_run.sh, verify:
PYTHON_SRC_DIR="/users/kir-fritzsche/oyk357/projects/Histology-Collagen-Quantification/python"

# The container will mount this over /app/python
# Changes to files here will be seen by the container
```

### "Output looks different with --scaling 2"

This is expected - you're processing at 1/2 resolution. To verify quality:

```bash
# Process same image with and without scaling
python python/decon.py -i input.czi -o output_full/ --scaling 1
python python/decon.py -i input.czi -o output_half/ --scaling 2

# Compare segmentation results
python python/seg.py -i output_full/PSR.ome.tiff -o seg_full.csv
python python/seg.py -i output_half/PSR.ome.tiff -o seg_half.csv

# Check if collagen percentages are similar
# Small differences (<5%) are usually acceptable
```

---

## 📚 Next Steps

After testing quick wins:

1. **Read full analysis**: See `docs/performance_analysis.md` for detailed explanation
2. **Consider Zarr conversion**: For long-term (100+ images), convert to OME-Zarr format (5-10x speedup)
3. **Optimize deconvolution**: After fixing I/O, profile the color deconvolution step

---

## 💡 Key Insights from Your Profiling

```
✓ File open:    0.192s  (negligible)
✓ Metadata:     0.000s  (negligible)
✓ Get bboxes:   0.298s  (negligible)
✗ Read tiles:   38.4s   (96.3% - THE BOTTLENECK)
✓ Stitch:       1.5s    (3.7% - already fast)
```

**Conclusion**: Fix the tile reading, everything else is already fast.

**Why threading doesn't help**:
- Disk I/O is the bottleneck (not CPU)
- Adding threads just creates I/O contention
- Sequential with optimized order > parallel with random order

---

## Questions?

- Check `docs/performance_analysis.md` for detailed explanations
- See `doc/workflows.md` for parameter documentation
- Open GitHub issue for bugs/feature requests
