#!/usr/bin/env python3
"""
Quick diagnostic script to compare pytest speed vs. real loading speed.

This helps understand why pytest passes fast but actual loading is slow.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "dependency" / "pyHisto"))

from pyHisto.io import czi_read
import aicspylibczi


def main():
    # Auto-detect container vs local execution
    if Path("/data").is_dir() and any(Path("/data").iterdir()):
        # Running in container
        czi_path = "/data/2025_03_04__11_33__0116-Split Scenes (Write files)-01-Scene-1-ScanRegion0.czi"
    else:
        # Running locally
        czi_path = "/well/kir-fritzsche/projects/archive/Nan/Nan_Fast_Green_PSR_Staining/split_scene/2025_03_04__11_33__0116-Split Scenes (Write files)-01-Scene-1-ScanRegion0.czi"

    if not Path(czi_path).exists():
        print(f"Error: File not found at {czi_path}")
        print("Please update the path in this script or provide as argument.")
        sys.exit(1)

    print("="*70)
    print("CZI Loading Speed Comparison")
    print("="*70)
    print(f"\nFile: {Path(czi_path).name}\n")

    # Get total tile count
    image = aicspylibczi.CziFile(Path(czi_path))
    dims = image.get_dims_shape()[0]
    total_tiles = dims.get('M', (0, 0))[1]
    image.close()

    print(f"Total tiles in file: {total_tiles}\n")

    # Test 1: Pytest-like (4 tiles, parallel)
    print("-" * 70)
    print("Test 1: Pytest-like loading (4 tiles, 2 workers)")
    print("-" * 70)
    start = time.time()
    img1 = czi_read(czi_path, channel=-1, scene=0, parallel=True,
                    n_workers=2, batch_size=2, max_tiles=4)
    t1 = time.time() - start
    print(f"✓ Loaded {img1.shape} in {t1:.3f}s")
    print(f"  Per-tile average: {t1/4:.3f}s\n")
    del img1

    # Test 2: Small subset (100 tiles, sequential)
    print("-" * 70)
    print("Test 2: Small subset sequential (100 tiles)")
    print("-" * 70)
    start = time.time()
    img2 = czi_read(czi_path, channel=-1, scene=0, parallel=False, max_tiles=100)
    t2 = time.time() - start
    print(f"✓ Loaded {img2.shape} in {t2:.3f}s")
    print(f"  Per-tile average: {t2/100:.3f}s")
    print(f"  Estimated full time: {t2/100 * total_tiles:.1f}s ({t2/100 * total_tiles/60:.1f} min)\n")
    del img2

    # Test 3: Small subset (100 tiles, parallel)
    print("-" * 70)
    print("Test 3: Small subset parallel (100 tiles, 8 workers)")
    print("-" * 70)
    start = time.time()
    img3 = czi_read(czi_path, channel=-1, scene=0, parallel=True,
                    n_workers=8, batch_size=50, max_tiles=100)
    t3 = time.time() - start
    print(f"✓ Loaded {img3.shape} in {t3:.3f}s")
    print(f"  Per-tile average: {t3/100:.3f}s")
    print(f"  Speedup vs sequential: {t2/t3:.2f}x")
    print(f"  Estimated full time: {t3/100 * total_tiles:.1f}s ({t3/100 * total_tiles/60:.1f} min)\n")
    del img3

    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nPytest speed (4 tiles):        {t1:.3f}s  ← Fast!")
    print(f"Sequential (100 tiles):        {t2:.3f}s")
    print(f"Parallel (100 tiles):          {t3:.3f}s")
    print(f"\nSpeedup from parallelization:  {t2/t3:.2f}x")
    print(f"\nEstimated time for {total_tiles} tiles:")
    print(f"  Sequential: {t2/100 * total_tiles/60:.1f} minutes")
    print(f"  Parallel:   {t3/100 * total_tiles/60:.1f} minutes")
    print(f"\nConclusion:")
    print(f"  Pytest is fast because it only loads {4} tiles.")
    print(f"  Your full dataset has {total_tiles} tiles ({total_tiles//4}x more).")

    if t2/t3 < 1.5:
        print(f"\n⚠️  WARNING: Parallel loading provides minimal speedup ({t2/t3:.2f}x).")
        print("  This suggests I/O is the bottleneck (disk speed, network latency).")
        print("  Recommendations:")
        print("    - Copy CZI file to local SSD before processing")
        print("    - Check if file is on slow network filesystem")
        print("    - Run profiling script to identify bottlenecks:")
        print("      python python/profile_czi_loading.py <file> --max-tiles 100")
    else:
        print(f"\n✓ Parallel loading provides good speedup ({t2/t3:.2f}x).")
        print("  Use parallel=True with n_workers=8 for best performance.")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
