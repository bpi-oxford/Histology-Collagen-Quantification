# CZI Tile Loading Benchmark and Profiling Tools

This directory contains tools to investigate and optimize CZI tile loading performance.

## Quick Start

### On BMRC (Recommended)

```bash
# Run via apptainer with interactive menu
bash scripts/bmrc_apptainer_run.sh
# Select option 6 (benchmark-czi) or 7 (profile-czi)

# Results will be saved to your DATA_DIR as:
# /path/to/data/benchmark_results_YYYYMMDD_HHMMSS.json
```

### Locally with Pixi/Conda

```bash
# Quick benchmark (100 tiles, 3 configurations, ~2-5 min)
python benchmark/benchmark_czi_loading.py /path/to/file.czi --max-tiles 100 --quick

# Full benchmark (all configurations)
python benchmark/benchmark_czi_loading.py /path/to/file.czi --max-tiles 500

# Detailed profiling to identify bottlenecks
python benchmark/profile_czi_loading.py /path/to/file.czi --max-tiles 100
```

### Path Auto-Detection

All benchmark scripts automatically detect if running inside a container:
- **Inside container**: Uses `/data/` paths (mounted from host DATA_DIR)
- **Local execution**: Uses full system paths like `/well/kir-fritzsche/...`

This ensures scripts work seamlessly in both environments without modification.

## Tools Overview

### 1. `benchmark_czi_loading.py` - Performance Comparison

**Purpose**: Compare different parallel loading strategies to find the fastest configuration.

**What it tests**:
- Sequential loading (baseline)
- Threading with 1, 2, 4, 8 workers
- Different batch sizes (10, 25, 50, 100 tiles per batch)
- Multiprocessing with 4, 8 workers

**Output**:
- Time taken for each configuration
- Memory usage
- Throughput (megapixels/second)
- Ranked summary of best configurations
- JSON results file for further analysis

**Usage**:
```bash
# Quick test (3 configs, ~2-5 minutes)
python benchmark/benchmark_czi_loading.py data.czi --max-tiles 100 --quick

# Medium test (all configs, ~10-20 minutes)
python benchmark/benchmark_czi_loading.py data.czi --max-tiles 500

# Full test (production-like, may take hours)
python benchmark/benchmark_czi_loading.py data.czi --output results.json
```

**Interpreting results**:
- Look for the configuration with lowest time
- Check if parallel loading provides speedup (2-4x typical)
- If threading is slower than sequential, investigate I/O bottlenecks
- If multiprocessing fails, it may be due to pickling issues or spawn overhead

### 2. `profile_czi_loading.py` - Bottleneck Identification

**Purpose**: Identify WHERE time is being spent in the loading process.

**Also see**: `profile_czi.sh` - Interactive wrapper with guided prompts

**What it measures**:
- File open time
- Metadata parsing time
- Bounding box retrieval time
- Per-tile read time (decompression + data access)
- Per-tile stitch time (memory copy)
- Transpose/finalization time

**Output**:
- Detailed timing breakdown for sampled tiles
- Average time per tile operation
- Percentage of time in read vs. stitch
- Estimated total time for full dataset

**Usage**:
```bash
# Interactive mode (recommended)
bash benchmark/profile_czi.sh

# Or direct invocation
# Profile 100 tiles (samples every 10th for detailed timing)
python benchmark/profile_czi_loading.py data.czi --max-tiles 100

# Profile specific channel/scene
python benchmark/profile_czi_loading.py data.czi --max-tiles 200 --channel 0 --scene 1
```

**Interpreting results**:
- **Read time >> Stitch time**: Bottleneck is I/O or decompression
  - Try parallel loading with threading
  - Check if disk is slow (network filesystem, etc.)
  - Consider pre-converting to uncompressed format

- **Stitch time >> Read time**: Bottleneck is memory operations
  - Unlikely but possible with very large tiles
  - Check if memory is being swapped to disk

- **High variance between tiles**: Some tiles are slow
  - May indicate disk cache misses
  - Or specific tiles have different compression

- **File open/metadata time is large**: Initial overhead
  - Not parallelizable, but amortized over many tiles

### 3. `benchmark_czi.sh` - Interactive Benchmark Wrapper

**Purpose**: User-friendly shell script with guided prompts for benchmarking.

**Features**:
- Auto-detects default CZI file path
- Offers quick/medium/full test modes
- Generates timestamped JSON output files
- Works in BMRC apptainer or local environment

**Usage**:
```bash
# Run with prompts
bash benchmark/benchmark_czi.sh

# Or via BMRC workflow
bash scripts/bmrc_apptainer_run.sh
# Select option 6 (benchmark-czi)
```

### 4. `profile_czi.sh` - Interactive Profile Wrapper

**Purpose**: User-friendly shell script with guided prompts for profiling.

**Features**:
- Auto-detects default CZI file path
- Offers quick/standard/detailed profiling options (50/100/200 tiles)
- Displays results directly to console (no file output)
- Works in BMRC apptainer or local environment

**Usage**:
```bash
# Run with prompts
bash benchmark/profile_czi.sh

# Or via BMRC workflow
bash scripts/bmrc_apptainer_run.sh
# Select option 7 (profile-czi)
```

### 5. `quick_test_czi.py` - Diagnostic Comparison

**Purpose**: Quick diagnostic to explain why pytest is fast vs. actual loading.

**What it tests**:
- Pytest-like loading (4 tiles, parallel)
- Small subset sequential (100 tiles)
- Small subset parallel (100 tiles, 8 workers)
- Estimates full dataset time
- Identifies if parallelization helps

**Usage**:
```bash
python benchmark/quick_test_czi.py
# Note: Hardcoded to default test file, edit path in script if needed
```

**Output**:
- Side-by-side comparison of speeds
- Speedup from parallelization
- Estimated time for full dataset
- Recommendations based on results

## Common Performance Issues and Solutions

### Issue 1: Threading is slower than sequential

**Symptoms**:
- Sequential loading: 2.0s
- Thread-8 loading: 5.0s

**Likely cause**: GIL contention or I/O serialization

**Solutions**:
- CZI library may not release GIL during decompression
- Try `parallel_mode="process"` instead of `"thread"`
- Check if filesystem is network-mounted and has poor concurrent access
- Consider reducing `n_workers` to match I/O capacity

### Issue 2: Multiprocessing fails or is very slow

**Symptoms**:
- Process-based loading fails with pickle errors
- Or much slower than threading

**Likely causes**:
- CziFile object cannot be pickled (spawned processes can't share handle)
- High overhead from process spawning and IPC
- Each process reopens the file (multiplies I/O)

**Solutions**:
- Use threading instead of multiprocessing
- If using multiprocessing, ensure batch_size is large (50-100+)
- Check if `mp_context="spawn"` is needed (vs. "fork")

### Issue 3: Very slow tile reads (>0.1s per tile)

**Symptoms**:
- Profile shows read_time dominates (>90%)
- Per-tile read time is high (>0.1s for typical tile)

**Likely causes**:
- Network filesystem latency (e.g., /well/... on BMRC)
- Highly compressed tiles require expensive decompression
- Sequential disk access pattern inefficient

**Solutions**:
- Copy CZI file to local SSD before processing
- Use parallel loading to overlap I/O with computation
- Check if CZI is on slow storage (lustre, NFS, etc.)
- Consider pre-extracting tiles or converting format

### Issue 4: Memory issues or OOM

**Symptoms**:
- Process killed by OOM
- Memory usage >> expected (image size * channels * 2)

**Likely causes**:
- Too many workers loading tiles simultaneously
- Batch size too large, accumulating tiles in memory
- Memory leak in aicspylibczi or underlying libraries

**Solutions**:
- Reduce `n_workers` (try 2-4 instead of 8)
- Reduce `batch_size` (try 10-25 instead of 50)
- Process tiles in smaller chunks with `max_tiles`
- Check memory usage in profiler output

## Expected Performance Ranges

### Fast (Good)
- Per-tile read: <0.01s
- Per-tile stitch: <0.001s
- Threading speedup: 2-4x vs. sequential
- Throughput: >100 Mpx/s

### Moderate (Acceptable)
- Per-tile read: 0.01-0.05s
- Per-tile stitch: 0.001-0.005s
- Threading speedup: 1.5-2x vs. sequential
- Throughput: 20-100 Mpx/s

### Slow (Needs investigation)
- Per-tile read: >0.1s
- Per-tile stitch: >0.01s
- Threading speedup: <1.2x or slower than sequential
- Throughput: <20 Mpx/s

## Recommended Workflow

1. **Start with profiling** (5 minutes):
   ```bash
   python benchmark/profile_czi_loading.py data.czi --max-tiles 100
   ```
   - Understand where time is spent
   - Check if read or stitch dominates
   - Get baseline per-tile timing

2. **Run quick benchmark** (5 minutes):
   ```bash
   python benchmark/benchmark_czi_loading.py data.czi --max-tiles 100 --quick
   ```
   - Compare sequential vs. thread-4 vs. thread-8
   - Identify if parallel loading helps

3. **If threading helps, optimize further** (20 minutes):
   ```bash
   python benchmark/benchmark_czi_loading.py data.czi --max-tiles 500
   ```
   - Test different worker counts
   - Test different batch sizes
   - Find optimal configuration

4. **Apply findings to production code**:
   - Update `dependency/pyHisto/pyHisto/io.py` defaults
   - Or pass optimal parameters when calling `czi_read()`
   - Document findings for future reference

## Comparing with pytest

If pytest runs fast but actual loading is slow, check:

```bash
# What does pytest do?
grep -A 20 "def test.*parallel.*subset" dependency/pyHisto/tests/test_read_czi.py
```

Likely pytest uses:
- `max_tiles=10` or similar small number
- Specific test file that's already cached
- Different parameters than production code

To replicate pytest performance:
```bash
python benchmark/benchmark_czi_loading.py data.czi --max-tiles 10
```

## Saving and Sharing Results

### Output File Locations

**On BMRC (via apptainer)**:
- Results are saved to your `DATA_DIR` (the directory containing your CZI files)
- Example: `/well/kir-fritzsche/projects/archive/Nan/.../benchmark_results_20251111_123456.json`
- This ensures results persist after the container exits

**Local execution**:
- Results are saved to the current directory or specified path
- Use `--output` to specify a custom location

### Manual Output Specification

```bash
# Save benchmark results with timestamp
python benchmark/benchmark_czi_loading.py data.czi \
  --max-tiles 500 \
  --output /path/to/results/benchmark_$(date +%Y%m%d_%H%M%S).json

# Results include:
# - All timing data
# - Configuration parameters
# - System info (CPU count, memory)
# - Image dimensions and throughput
```

### Interactive Script (Automatic Output)

```bash
# Using benchmark_czi.sh - automatically saves with timestamp
bash benchmark/benchmark_czi.sh
# Output: /data/benchmark_results_YYYYMMDD_HHMMSS.json (in container)
#     or: benchmark_results_YYYYMMDD_HHMMSS.json (local)
```

## Further Optimization Ideas

If benchmarks show poor performance:

1. **Pre-convert CZI to optimized format**:
   - Extract tiles to HDF5 or Zarr
   - Use uncompressed or fast compression
   - Trade disk space for read speed

2. **Use different CZI reader**:
   - Try bioio-czi reader instead of aicspylibczi
   - Check if pylibCZIrw is faster

3. **Lazy loading with Dask**:
   - Use `czi_dask_read()` in io.py
   - Process tiles on-demand
   - Better memory management for large images

4. **GPU acceleration**:
   - Move decompression or processing to GPU
   - Use CuPy instead of NumPy for array operations

5. **File system optimization**:
   - Copy to local SSD (/tmp or /scratch)
   - Use parallel filesystem (e.g., BeeGFS instead of Lustre)
   - Pre-fetch files with `dd` or similar

## Contact

For issues or questions:
- Check `doc/workflows.md` for general troubleshooting
- Review `dependency/pyHisto/pyHisto/io.py` source code
- Post issue to project maintainers
