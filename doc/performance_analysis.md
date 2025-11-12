# CZI Tile Loading Performance Analysis & Optimization Guide

**Date**: 2025-11-12
**Files Analyzed**:
- `results/benchmark/benchmark_results_20251111_180838.json`
- `results/benchmark/profile_2025_03_04__11_33__0116...50tiles.txt`
- `dependency/pyHisto/pyHisto/io.py`

---

## Executive Summary

**Current Performance**: Loading 50 tiles takes ~40 seconds (0.768s per tile), with **96.3% of time spent in disk I/O**.

**Key Finding**: Threading provides **NO speedup** (only 1.4% improvement from sequential to 8 threads), confirming that **random disk I/O is the bottleneck**, not CPU.

**Estimated full-image loading time**: For 723 tiles × 0.768s/tile = **~9.2 minutes per image** (read-only, before deconvolution).

---

## Root Cause Analysis

### 1. Random I/O Pattern (96.3% of execution time)

**Current Implementation** (`pyHisto/io.py:250-260`):
```python
# Sequential tile loading - one read_mosaic() call per tile
for _, bbox in tqdm(tile_items):
    image_tile = _read_tile_data(image, dims_shape, bbox, channel, ch_dim)
    # Each call requires: seek → read → decompress
```

**Problem**:
- CZI files store 723 tiles in compressed blocks scattered across the file
- Each `aicspylibczi.read_mosaic()` call performs a random disk seek
- Seek times on network storage (5-15ms) × 723 tiles = significant overhead
- Variable read times (0.52s → 0.98s) indicate seek pattern dependency

### 2. Threading Creates I/O Contention

**Benchmark Results**:
| Configuration | Time (s) | Speedup |
|---------------|----------|---------|
| Sequential    | 95.64    | 1.00x   |
| Thread-4      | 95.49    | 1.00x   |
| Thread-8      | 94.32    | 1.01x   |

**Why Threading Fails**:
- Bottleneck is disk I/O, not CPU
- Each thread opens its own file handle (`_process_tile_batch:59`)
- Multiple simultaneous random reads increase storage contention
- No benefit from parallelization when I/O-bound

### 3. Per-Tile Overhead Compounds

**Profiling data** (50 tiles):
- Read time per tile: 0.768s average (96.3% of time)
- Stitch time per tile: 0.030s average (3.7% of time)
- One-time overhead: 0.490s (negligible)

**Extrapolation**:
- 723 tiles × 0.768s = **9.2 minutes** per full image (I/O only)
- Additional time for deconvolution processing on top

---

## Optimization Strategies (Prioritized by Impact)

### ⭐ **Strategy 1: Read Tiles in Spatial Order** (HIGH IMPACT - 20-40% improvement)

**Rationale**: Reading tiles in file order minimizes seek distance and may enable sequential reads.

**Implementation** (modify `pyHisto/io.py:219`):

```python
# Current: tiles read in index order (0, 1, 2, ...)
tile_items = [(idx, tile_bboxes[idx]) for idx in tile_indices]

# Proposed: sort by spatial coordinates (Y-major, then X)
tile_items_sorted = sorted(tile_items, key=lambda t: (t[1]["y"], t[1]["x"]))
```

**Expected Benefit**:
- Reduces average seek distance between tiles
- May enable read-ahead buffering by OS
- 20-40% speed improvement (estimated 60-75s instead of 95s)

**Trade-offs**: None (free performance gain)

---

### ⭐ **Strategy 2: Reduce Tile Count via Downsampling** (HIGH IMPACT - 2-4x improvement)

**Rationale**: Fewer tiles = fewer I/O operations. For collagen quantification, full resolution may not be necessary.

**Implementation** (use existing `--scaling` parameter in `decon.py`):

```bash
# Process at 1/2 resolution (1/4 tiles)
python python/decon.py --scaling 2 -i input.czi -o output/

# Process at 1/4 resolution (1/16 tiles)
python python/decon.py --scaling 4 -i input.czi -o output/
```

**Expected Benefit**:
- `--scaling 2`: 4x fewer tiles → ~2.5 minutes instead of 9.2 minutes
- `--scaling 4`: 16x fewer tiles → ~35 seconds
- Quadratic reduction in tile count (scaling²)

**Trade-offs**:
- Lower resolution output
- May be acceptable for tissue-level collagen quantification
- Test with your specific analysis requirements

---

### ⭐⭐ **Strategy 3: Batch Adjacent Tiles** (MEDIUM IMPACT - 30-50% improvement)

**Rationale**: Read multiple spatially-adjacent tiles in one I/O operation.

**Implementation** (requires modification to `pyHisto/io.py`):

```python
def _read_tile_region(image, tile_group, dims_shape, channel, ch_dim):
    """
    Read a rectangular region covering multiple adjacent tiles.
    Then slice into individual tiles.
    """
    # Calculate bounding box covering all tiles in group
    min_x = min(t["x"] for t in tile_group)
    max_x = max(t["x"] + t["w"] for t in tile_group)
    min_y = min(t["y"] for t in tile_group)
    max_y = max(t["y"] + t["h"] for t in tile_group)

    # Single read for entire region
    region = image.read_mosaic((min_x, min_y, max_x - min_x, max_y - min_y), C=channel)

    # Extract individual tiles from region
    tiles = []
    for tile_bbox in tile_group:
        x_off = tile_bbox["x"] - min_x
        y_off = tile_bbox["y"] - min_y
        tile = region[:, y_off:y_off+tile_bbox["h"], x_off:x_off+tile_bbox["w"]]
        tiles.append(tile)

    return tiles

# Group adjacent tiles (e.g., 2x2 grid = 4 tiles per read)
tile_groups = group_adjacent_tiles(tile_items, grid_size=2)
for group in tile_groups:
    tiles = _read_tile_region(image, group, dims_shape, channel, ch_dim)
```

**Expected Benefit**:
- 4 tiles per read → 4x fewer I/O operations
- Reduces 723 reads to ~180 reads
- 30-50% speed improvement

**Trade-offs**:
- Requires careful handling of tile boundaries
- May read extra "dead space" between tiles (wasted bandwidth)
- Needs validation for your specific CZI tile layout

---

### ⭐⭐ **Strategy 4: Switch to Memory-Mapped I/O** (MEDIUM IMPACT - variable)

**Rationale**: Let OS handle caching and prefetching instead of explicit reads.

**Implementation** (requires checking if `aicspylibczi` supports mmap):

```python
# Check if aicspylibczi can open in memory-mapped mode
# Alternatively, use bioio with zarr backend
```

**Expected Benefit**:
- OS-level caching can cache frequently accessed regions
- Prefetching can reduce latency for sequential access
- 10-30% improvement if tiles are accessed in predictable patterns

**Trade-offs**:
- Requires sufficient RAM for OS page cache
- May not work well on network storage (NFS)
- Benefits depend on OS and filesystem

---

### ⭐⭐⭐ **Strategy 5: Use Alternative File Format** (HIGH IMPACT LONG-TERM - 5-10x improvement)

**Rationale**: CZI is optimized for acquisition, not for batch processing. Modern formats like OME-Zarr are optimized for cloud-scale analysis.

**Implementation**:

```bash
# One-time conversion: CZI → OME-Zarr
bioformats2raw input.czi output.zarr
# Or use bioio:
python -c "from bioio import BioImage; img=BioImage('input.czi'); img.save('output.zarr')"

# Then process from zarr (supports efficient chunked reading)
python python/decon.py -i output.zarr -o results/
```

**Expected Benefit**:
- Zarr stores tiles in chunked, uncompressed or lightly-compressed format
- Optimized for random access patterns
- 5-10x faster tile loading (especially with cloud storage)
- Enables Dask-based parallel processing

**Trade-offs**:
- Requires one-time conversion step
- Zarr files may be larger than CZI (less compression)
- May not preserve all CZI metadata

---

### 🔬 **Strategy 6: Profile Filesystem I/O** (DIAGNOSTIC)

**Rationale**: Understand if the bottleneck is disk bandwidth, latency, or filesystem overhead.

**Implementation**:

```bash
# Run with iostat to monitor disk I/O during loading
iostat -x 1 > iostat_log.txt &
IOSTAT_PID=$!

python benchmark/profile_czi_loading.py input.czi --max-tiles 100

kill $IOSTAT_PID

# Analyze iostat_log.txt for:
# - %util (disk utilization)
# - await (average I/O wait time)
# - r/s (reads per second)
```

**Interpretation**:
- High `await` (>20ms): Seek time dominates → use Strategy 1 or 2
- Low `r/s` (<10): Too few concurrent reads → not a threading problem
- High `%util` (>80%): Disk saturated → need better file format (Strategy 5)

---

## Recommended Implementation Plan

### **Phase 1: Quick Wins (Immediate - 0 days)**

1. **Test downsampling** (Strategy 2):
   ```bash
   bash python/decon.sh
   # When prompted for scaling, try 2 or 4
   # Verify output quality is acceptable for your analysis
   ```

2. **Profile with iostat** (Strategy 6):
   ```bash
   # Understand your specific I/O patterns
   iostat -x 1 > iostat.log &
   bash scripts/bmrc_apptainer_run.sh  # Select debug workflow
   ```

### **Phase 2: Code Modifications (1-2 days)**

3. **Implement spatial sorting** (Strategy 1):
   - Modify `dependency/pyHisto/pyHisto/io.py:219`
   - Sort `tile_items` by Y, then X coordinates
   - Test with benchmark script

   **Expected**: 20-40% improvement (95s → 60-75s)

4. **Optional: Implement tile batching** (Strategy 3):
   - Add `_read_tile_region()` function to `io.py`
   - Group adjacent tiles (2×2 or 3×3)
   - Test memory usage carefully

   **Expected**: Additional 20-30% improvement (60s → 40-50s)

### **Phase 3: Infrastructure Changes (1 week)**

5. **Convert to OME-Zarr** (Strategy 5):
   - Convert sample CZI files to Zarr format
   - Validate metadata preservation (pixel size, channels)
   - Update `decon.py` to support Zarr input
   - Benchmark against CZI

   **Expected**: 5-10x improvement (95s → 10-20s per image)

---

## Testing & Validation

### Benchmark Command

```bash
# Test current performance
time python benchmark/benchmark_czi_loading.py \
    /path/to/input.czi \
    --max-tiles 100 \
    --quick \
    --output results/benchmark_baseline.json

# After modifications, compare
time python benchmark/benchmark_czi_loading.py \
    /path/to/input.czi \
    --max-tiles 100 \
    --quick \
    --output results/benchmark_optimized.json
```

### Validation Checklist

- [ ] Output image dimensions match original
- [ ] Output pixel values match (within numerical precision)
- [ ] Tile stitching has no visible seams
- [ ] All tiles successfully loaded (no missing data)
- [ ] Memory usage stays within acceptable limits
- [ ] Downstream segmentation results unchanged

---

## Additional Considerations

### Storage System Specifics

Your system uses **BMRC cluster with `/well/` shared storage**, likely NFS:

**NFS-specific optimizations**:
1. Use larger read buffer sizes (if configurable)
2. Minimize metadata operations (stat, open/close)
3. Consider caching frequently-used files on local node storage
4. Use `--scaling` parameter to reduce I/O volume

### Long-term Architecture

For pipelines processing hundreds/thousands of images:

1. **Pre-convert to Zarr**: One-time conversion step in data ingestion pipeline
2. **Use Dask distributed**: Scale across multiple BMRC nodes
3. **Implement tile cache**: Store frequently-accessed tiles in fast local storage
4. **Region-based processing**: Process by anatomical region (if applicable) to maximize spatial locality

---

## Questions for Further Optimization

1. **What is the acceptable resolution for collagen quantification?**
   - Can you use `--scaling 2` or `--scaling 4` without losing analytical accuracy?
   - Test with validation dataset

2. **Is the CZI tile layout grid-aligned or scattered?**
   - Affects viability of tile batching (Strategy 3)
   - Can visualize with: `python -c "from pyHisto.io import czi_read; import matplotlib; ..."`

3. **What is the filesystem type for `/well/` storage?**
   - NFS, Lustre, GPFS, or other?
   - Different filesystems have different optimization strategies

4. **How many images need to be processed per experiment?**
   - If hundreds/thousands: invest in Zarr conversion (Strategy 5)
   - If <10: just use downsampling (Strategy 2)

---

## Summary of Expected Improvements

| Strategy | Complexity | Expected Speedup | Notes |
|----------|-----------|------------------|-------|
| 1. Spatial sorting | Low | 1.3-1.7x | Free performance, no trade-offs |
| 2. Downsampling (--scaling 2) | None | 2-3x | Test quality impact |
| 2. Downsampling (--scaling 4) | None | 8-15x | May be too low resolution |
| 3. Tile batching | Medium | 1.3-1.5x | Requires code changes |
| 4. Memory mapping | Medium | 1.1-1.3x | OS-dependent |
| 5. Convert to Zarr | High | 5-10x | Best long-term solution |

**Combined**: Strategies 1+2 could achieve **3-5x speedup** with minimal changes.

---

## Contact & Support

For implementation questions:
- Check `doc/workflows.md` for parameter explanations
- See `notebook/collagen_quantification_mouse.ipynb` for technical details
- Open GitHub issue for pyHisto-specific changes

