# CZI Tile Loading Performance Findings

**Date**: 2025-11-12
**Analysis of**: 50 tiles benchmark + profiling on BMRC cluster

---

## Summary

**Bottleneck**: Random disk I/O dominates (96.3% of execution time)
**Current Performance**: ~0.77 seconds per tile → 9.2 minutes for 723-tile image
**Threading Impact**: None (only 1.4% speedup with 8 threads vs sequential)

---

## Key Metrics

| Metric | Value | Impact |
|--------|-------|--------|
| **Tile read time** | 96.3% of total | Major bottleneck |
| **Tile stitch time** | 3.7% of total | Already optimized |
| **Threading speedup** | 1.01x (negligible) | I/O-bound, not CPU-bound |
| **Read time variance** | 0.52s - 0.98s | Random disk seeks |

**Benchmark Results** (50 tiles):
- Sequential: 95.64s
- Thread-4: 95.49s (0.2% faster)
- Thread-8: 94.32s (1.4% faster)

**Profiling Breakdown** (per tile average):
- Read: 0.768s (96.3%)
- Stitch: 0.030s (3.7%)
- Overhead: 0.490s (one-time, negligible)

---

## Root Cause

**Problem**: Each of 723 tiles requires:
1. Random disk seek to tile location in CZI file
2. Read compressed tile data
3. Decompress tile

**Why threading fails**: Multiple threads create I/O contention on shared storage (BMRC `/well/`), making random seeks worse.

---

## Recommended Actions

### Immediate (for current data processing)

**1. Use sequential loading** (already fastest option)
- Set `parallel=False` in `czi_read()` calls
- Avoid threading overhead
- **Status**: Implemented in decon.py

**2. Enable downsampling** (2-4x faster, acceptable quality)
- Use `--scaling 2` parameter in decon.py
- Reduces tiles by 4x → faster processing
- Validate output quality for collagen quantification

### Future Optimization (if processing >100 images)

**3. Apply spatial sorting** (20-40% improvement)
- Sort tiles by Y-then-X coordinates before reading
- Reduces average disk seek distance
- See `patches/optimize_tile_loading.patch`

**4. Convert to OME-Zarr format** (5-10x improvement)
- One-time conversion: CZI → Zarr
- Optimized for chunked random access
- Best for batch processing pipelines

---

## Impact on Workflow

**Current decon.py settings**:
- Uses `parallel=False` (correct choice based on benchmarks)
- Processing time dominated by I/O, not deconvolution compute

**Expected full-pipeline time** (per image, 723 tiles):
- Tile loading: ~9 minutes (I/O-bound)
- Color deconvolution: ~2-5 minutes (depends on tile_size, batch_num)
- **Total**: ~12-15 minutes per full-resolution image

**With --scaling 2**:
- Tile loading: ~2.5 minutes
- Deconvolution: ~0.5-1 minute
- **Total**: ~3-4 minutes per image

---

## References

- Full analysis: `performance_analysis.md`
- Quick start guide: `OPTIMIZATION_QUICKSTART.md`
- Benchmark data: `../results/benchmark/`
