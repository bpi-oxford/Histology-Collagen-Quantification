#!/usr/bin/env python3
"""
Benchmark CZI tile loading performance with different strategies.

Usage:
    python benchmark_czi_loading.py /path/to/file.czi [--max-tiles N]
"""

import argparse
import sys
import time
import psutil
import os
from pathlib import Path
import json

# Add parent directory to path for pyHisto import
sys.path.insert(0, str(Path(__file__).parent.parent / "dependency" / "pyHisto"))

from pyHisto.io import czi_read


def get_memory_usage():
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def benchmark_loading(path, config, max_tiles=None):
    """
    Benchmark a single loading configuration.

    Args:
        path: Path to CZI file
        config: Dict with keys: parallel, parallel_mode, n_workers, batch_size
        max_tiles: Optional limit on number of tiles to load

    Returns:
        Dict with timing and memory info
    """
    label = config.get("label", "unknown")

    print(f"\n{'='*70}")
    print(f"Testing: {label}")
    print(f"  parallel={config['parallel']}, mode={config.get('parallel_mode', 'N/A')}, "
          f"workers={config.get('n_workers', 'N/A')}, batch_size={config.get('batch_size', 'N/A')}")
    if max_tiles:
        print(f"  max_tiles={max_tiles}")
    print(f"{'='*70}")

    mem_before = get_memory_usage()
    start_time = time.time()

    try:
        image = czi_read(
            path,
            channel=-1,
            scene=0,
            parallel=config["parallel"],
            parallel_mode=config.get("parallel_mode", "thread"),
            n_workers=config.get("n_workers", None),
            batch_size=config.get("batch_size", 50),
            verbose=False,
            max_tiles=max_tiles
        )

        elapsed = time.time() - start_time
        mem_after = get_memory_usage()
        mem_used = mem_after - mem_before

        result = {
            "label": label,
            "success": True,
            "elapsed_seconds": elapsed,
            "memory_mb": mem_used,
            "image_shape": image.shape,
            "image_dtype": str(image.dtype),
            **config
        }

        print(f"\n✓ SUCCESS")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Memory: {mem_used:.1f} MB")
        print(f"  Output shape: {image.shape}")
        print(f"  Throughput: {image.shape[0] * image.shape[1] / elapsed / 1e6:.2f} Mpx/s")

        # Clean up
        del image

    except Exception as e:
        elapsed = time.time() - start_time
        result = {
            "label": label,
            "success": False,
            "elapsed_seconds": elapsed,
            "error": str(e),
            **config
        }

        print(f"\n✗ FAILED")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Error: {e}")

    return result


def run_benchmarks(czi_path, max_tiles=None, quick=False):
    """
    Run a series of benchmarks with different configurations.

    Args:
        czi_path: Path to CZI file
        max_tiles: Optional limit on tiles for testing
        quick: If True, run only essential tests
    """

    if not Path(czi_path).exists():
        print(f"Error: File not found: {czi_path}")
        return []

    print(f"\nBenchmarking CZI loading: {Path(czi_path).name}")
    print(f"System: {psutil.cpu_count()} CPUs, {psutil.virtual_memory().total / 1024**3:.1f} GB RAM")

    # Define test configurations
    if quick:
        configs = [
            {"label": "Sequential", "parallel": False},
            {"label": "Thread-4", "parallel": True, "parallel_mode": "thread", "n_workers": 4, "batch_size": 50},
            {"label": "Thread-8", "parallel": True, "parallel_mode": "thread", "n_workers": 8, "batch_size": 50},
        ]
    else:
        configs = [
            # Sequential baseline
            {"label": "Sequential", "parallel": False},

            # Threading with different worker counts
            {"label": "Thread-1", "parallel": True, "parallel_mode": "thread", "n_workers": 1, "batch_size": 50},
            {"label": "Thread-2", "parallel": True, "parallel_mode": "thread", "n_workers": 2, "batch_size": 50},
            {"label": "Thread-4", "parallel": True, "parallel_mode": "thread", "n_workers": 4, "batch_size": 50},
            {"label": "Thread-8", "parallel": True, "parallel_mode": "thread", "n_workers": 8, "batch_size": 50},

            # Threading with different batch sizes (8 workers)
            {"label": "Thread-8-batch10", "parallel": True, "parallel_mode": "thread", "n_workers": 8, "batch_size": 10},
            {"label": "Thread-8-batch25", "parallel": True, "parallel_mode": "thread", "n_workers": 8, "batch_size": 25},
            {"label": "Thread-8-batch100", "parallel": True, "parallel_mode": "thread", "n_workers": 8, "batch_size": 100},

            # Multiprocessing (if safe)
            {"label": "Process-4", "parallel": True, "parallel_mode": "process", "n_workers": 4, "batch_size": 50},
            {"label": "Process-8", "parallel": True, "parallel_mode": "process", "n_workers": 8, "batch_size": 50},
        ]

    results = []
    for config in configs:
        result = benchmark_loading(czi_path, config, max_tiles)
        results.append(result)

        # Brief pause between tests
        time.sleep(1)

    return results


def print_summary(results):
    """Print comparison summary of all results."""
    print(f"\n\n{'='*70}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*70}\n")

    # Filter successful results
    successful = [r for r in results if r["success"]]

    if not successful:
        print("No successful runs to compare.")
        return

    # Sort by elapsed time
    successful.sort(key=lambda x: x["elapsed_seconds"])

    print(f"{'Rank':<6} {'Configuration':<25} {'Time (s)':<12} {'Memory (MB)':<15} {'Throughput (Mpx/s)':<20}")
    print("-" * 70)

    baseline_time = successful[0]["elapsed_seconds"]

    for i, result in enumerate(successful, 1):
        label = result["label"]
        time_s = result["elapsed_seconds"]
        mem_mb = result.get("memory_mb", 0)

        # Calculate throughput
        if "image_shape" in result:
            shape = result["image_shape"]
            throughput = shape[0] * shape[1] / time_s / 1e6
            throughput_str = f"{throughput:.2f}"
        else:
            throughput_str = "N/A"

        speedup = baseline_time / time_s
        speedup_str = f"({speedup:.2f}x)" if i > 1 else "(baseline)"

        print(f"{i:<6} {label:<25} {time_s:<12.2f} {mem_mb:<15.1f} {throughput_str:<20}")

    print("\n" + "="*70)
    print(f"Best configuration: {successful[0]['label']}")
    print(f"Time: {successful[0]['elapsed_seconds']:.2f}s")

    # Identify failures
    failed = [r for r in results if not r["success"]]
    if failed:
        print(f"\nFailed configurations ({len(failed)}):")
        for r in failed:
            print(f"  - {r['label']}: {r.get('error', 'Unknown error')}")


def save_results(results, output_path):
    """Save benchmark results to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark CZI tile loading with different parallel strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test with 100 tiles
  python benchmark_czi_loading.py data.czi --max-tiles 100 --quick

  # Full benchmark (may take a while)
  python benchmark_czi_loading.py data.czi

  # Test specific tile count
  python benchmark_czi_loading.py data.czi --max-tiles 500 --output results.json
        """
    )

    parser.add_argument(
        "czi_file",
        help="Path to CZI file to benchmark"
    )

    parser.add_argument(
        "--max-tiles",
        type=int,
        default=None,
        help="Limit number of tiles to load (for quick testing, e.g., 100)"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only essential tests (sequential, thread-4, thread-8)"
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Save results to JSON file"
    )

    args = parser.parse_args()

    # Run benchmarks
    results = run_benchmarks(args.czi_file, args.max_tiles, args.quick)

    # Print summary
    print_summary(results)

    # Save results if requested
    if args.output:
        save_results(results, args.output)


if __name__ == "__main__":
    main()
