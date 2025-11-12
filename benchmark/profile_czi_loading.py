#!/usr/bin/env python3
"""
Profile CZI tile loading to identify bottlenecks.

This script instruments the tile loading process to measure:
- Time spent opening CZI files
- Time per tile read operation
- Time spent in data copying/stitching
- Memory allocation patterns
"""

import sys
import time
import pathlib
from pathlib import Path
import numpy as np
from collections import defaultdict
import argparse

# Add parent directory for pyHisto
sys.path.insert(0, str(Path(__file__).parent.parent / "dependency" / "pyHisto"))

import aicspylibczi


def profile_sequential_loading(path, max_tiles=100, channel=-1, scene=0):
    """
    Profile sequential tile loading with detailed timing breakdown.

    Args:
        path: Path to CZI file
        max_tiles: Number of tiles to load
        channel: Channel to load (-1 for all)
        scene: Scene index
    """
    print(f"\n{'='*70}")
    print("DETAILED TILE LOADING PROFILE")
    print(f"{'='*70}\n")

    timings = defaultdict(list)

    # Phase 1: Open file
    t0 = time.time()
    image = aicspylibczi.CziFile(pathlib.Path(path))
    timings['file_open'].append(time.time() - t0)
    print(f"✓ File opened in {timings['file_open'][0]:.3f}s")

    # Phase 2: Get metadata
    t0 = time.time()
    dims_shape = image.get_dims_shape()[0]
    timings['metadata'].append(time.time() - t0)

    # Determine channel dimension
    has_c = 'C' in dims_shape
    has_a = 'A' in dims_shape

    if has_a:
        ch_dim = "A"
        n_channels = dims_shape['A'][1] if channel == -1 else 1
    elif has_c:
        ch_dim = "C"
        n_channels = dims_shape['C'][1] if channel == -1 else 1
    else:
        ch_dim = None
        n_channels = 1

    # Get total tiles
    if 'M' in dims_shape:
        total_tiles = dims_shape['M'][1]
    else:
        raise ValueError("No mosaic dimension 'M' found")

    n_tiles = min(max_tiles, total_tiles) if max_tiles else total_tiles

    print(f"✓ Metadata parsed in {timings['metadata'][0]:.3f}s")
    print(f"  Total tiles: {total_tiles}, Loading: {n_tiles}")
    print(f"  Channel dimension: {ch_dim}, Channels: {n_channels}\n")

    # Phase 3: Get bounding boxes
    print("Getting tile bounding boxes...")
    t0 = time.time()
    tile_bboxes = {}

    for m_idx in range(n_tiles):
        try:
            if ch_dim == "C":
                c_idx = 0 if channel == -1 else channel
                bbox = image.get_mosaic_tile_bounding_box(M=m_idx, S=scene, C=c_idx)
            elif ch_dim == "A":
                bbox = image.get_mosaic_tile_bounding_box(M=m_idx, S=scene, C=0)
            else:
                bbox = image.get_mosaic_tile_bounding_box(M=m_idx, S=scene)

            tile_bboxes[m_idx] = {
                "x": bbox.x,
                "y": bbox.y,
                "w": bbox.w,
                "h": bbox.h
            }
        except Exception as e:
            print(f"  Warning: Could not get bbox for tile {m_idx}: {e}")

    timings['get_bboxes'].append(time.time() - t0)
    print(f"✓ Got {len(tile_bboxes)} bounding boxes in {timings['get_bboxes'][0]:.3f}s")

    # Phase 4: Calculate output dimensions
    t0 = time.time()
    min_x = min(bbox["x"] for bbox in tile_bboxes.values())
    max_x = max(bbox["x"] for bbox in tile_bboxes.values())
    min_y = min(bbox["y"] for bbox in tile_bboxes.values())
    max_y = max(bbox["y"] for bbox in tile_bboxes.values())

    first_bbox = tile_bboxes[0]
    tile_w = first_bbox["w"]
    tile_h = first_bbox["h"]

    output_width = max_x - min_x + tile_w
    output_height = max_y - min_y + tile_h

    timings['calc_dims'].append(time.time() - t0)
    print(f"✓ Calculated output dimensions: {output_width}x{output_height} in {timings['calc_dims'][0]:.3f}s")
    print(f"  Individual tile size: {tile_w}x{tile_h}")

    # Phase 5: Allocate output array
    t0 = time.time()
    output = np.zeros((output_height, output_width, n_channels), dtype=np.uint16)
    timings['allocate'].append(time.time() - t0)
    mem_mb = output.nbytes / 1024 / 1024
    print(f"✓ Allocated output array in {timings['allocate'][0]:.3f}s ({mem_mb:.1f} MB)\n")

    # Phase 6: Load tiles with detailed timing
    print(f"Loading {n_tiles} tiles (sampling every 10th for detailed timing)...\n")

    sample_interval = max(1, n_tiles // 10)  # Sample 10 tiles evenly
    detailed_samples = []

    for idx, (m_idx, bbox) in enumerate(tile_bboxes.items()):
        should_profile = (idx % sample_interval == 0)

        if should_profile:
            # Detailed timing for this tile
            t_total = time.time()

            # Read tile
            t_read = time.time()
            try:
                if ch_dim == "C":
                    chs = dims_shape['C'][1]
                    if channel == -1:
                        tile = []
                        for c in range(chs):
                            tile.append(image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]), C=c))
                        tile = np.concatenate(tile, axis=0)
                        image_tile = np.transpose(tile, (1, 2, 0)).astype(np.uint16)
                    else:
                        tile = image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]), C=channel)
                        image_tile = np.transpose(tile, (1, 2, 0)).astype(np.uint16)
                elif ch_dim == "A":
                    tile = image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]), C=0)
                    image_tile = tile[0, :, :, :].astype(np.uint16)
                else:
                    tile = image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]))
                    image_tile = np.transpose(tile, (1, 2, 0)).astype(np.uint16)
                    if image_tile.ndim == 2:
                        image_tile = image_tile[..., np.newaxis]

                read_time = time.time() - t_read

                # Stitch tile
                t_stitch = time.time()
                y_start = bbox["y"] - min_y
                y_end = y_start + bbox["h"]
                x_start = bbox["x"] - min_x
                x_end = x_start + bbox["w"]
                output[y_start:y_end, x_start:x_end] = image_tile
                stitch_time = time.time() - t_stitch

                total_time = time.time() - t_total

                detailed_samples.append({
                    'tile_idx': idx,
                    'read_time': read_time,
                    'stitch_time': stitch_time,
                    'total_time': total_time
                })

                print(f"  Tile {idx:4d}: read={read_time:.4f}s, stitch={stitch_time:.4f}s, total={total_time:.4f}s")

            except Exception as e:
                print(f"  Tile {idx:4d}: FAILED - {e}")

        else:
            # Fast path without detailed timing
            try:
                if ch_dim == "C":
                    chs = dims_shape['C'][1]
                    if channel == -1:
                        tile = []
                        for c in range(chs):
                            tile.append(image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]), C=c))
                        tile = np.concatenate(tile, axis=0)
                        image_tile = np.transpose(tile, (1, 2, 0)).astype(np.uint16)
                    else:
                        tile = image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]), C=channel)
                        image_tile = np.transpose(tile, (1, 2, 0)).astype(np.uint16)
                elif ch_dim == "A":
                    tile = image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]), C=0)
                    image_tile = tile[0, :, :, :].astype(np.uint16)
                else:
                    tile = image.read_mosaic((bbox["x"], bbox["y"], bbox["w"], bbox["h"]))
                    image_tile = np.transpose(tile, (1, 2, 0)).astype(np.uint16)
                    if image_tile.ndim == 2:
                        image_tile = image_tile[..., np.newaxis]

                y_start = bbox["y"] - min_y
                y_end = y_start + bbox["h"]
                x_start = bbox["x"] - min_x
                x_end = x_start + bbox["w"]
                output[y_start:y_end, x_start:x_end] = image_tile

            except Exception as e:
                pass  # Skip failed tiles in non-profiled path

    # Phase 7: Finalize
    t0 = time.time()
    output = np.transpose(output, (1, 0, 2))
    timings['transpose'].append(time.time() - t0)

    try:
        image.close()
    except AttributeError:
        pass

    # Summary statistics
    print(f"\n{'='*70}")
    print("PROFILING SUMMARY")
    print(f"{'='*70}\n")

    if detailed_samples:
        avg_read = np.mean([s['read_time'] for s in detailed_samples])
        avg_stitch = np.mean([s['stitch_time'] for s in detailed_samples])
        avg_total = np.mean([s['total_time'] for s in detailed_samples])

        print(f"Per-tile averages (from {len(detailed_samples)} sampled tiles):")
        print(f"  Read time:   {avg_read:.4f}s")
        print(f"  Stitch time: {avg_stitch:.4f}s")
        print(f"  Total time:  {avg_total:.4f}s")
        print(f"  Read %:      {100 * avg_read / avg_total:.1f}%")
        print(f"  Stitch %:    {100 * avg_stitch / avg_total:.1f}%")

        # Extrapolate to full dataset
        estimated_total = avg_total * n_tiles
        print(f"\nEstimated time for {n_tiles} tiles: {estimated_total:.1f}s ({estimated_total/60:.1f} min)")

    print(f"\nOne-time overhead:")
    print(f"  File open:    {timings['file_open'][0]:.3f}s")
    print(f"  Metadata:     {timings['metadata'][0]:.3f}s")
    print(f"  Get bboxes:   {timings['get_bboxes'][0]:.3f}s")
    print(f"  Calc dims:    {timings['calc_dims'][0]:.3f}s")
    print(f"  Allocate:     {timings['allocate'][0]:.3f}s")
    print(f"  Transpose:    {timings['transpose'][0]:.3f}s")

    overhead_total = sum([
        timings['file_open'][0],
        timings['metadata'][0],
        timings['get_bboxes'][0],
        timings['calc_dims'][0],
        timings['allocate'][0],
        timings['transpose'][0]
    ])
    print(f"  Total overhead: {overhead_total:.3f}s")

    print(f"\n{'='*70}\n")

    return output, timings, detailed_samples


def main():
    parser = argparse.ArgumentParser(
        description="Profile CZI tile loading to identify bottlenecks"
    )

    parser.add_argument(
        "czi_file",
        help="Path to CZI file"
    )

    parser.add_argument(
        "--max-tiles",
        type=int,
        default=100,
        help="Number of tiles to load for profiling (default: 100)"
    )

    parser.add_argument(
        "--channel",
        type=int,
        default=-1,
        help="Channel to load (-1 for all channels, default: -1)"
    )

    parser.add_argument(
        "--scene",
        type=int,
        default=0,
        help="Scene index (default: 0)"
    )

    args = parser.parse_args()

    if not Path(args.czi_file).exists():
        print(f"Error: File not found: {args.czi_file}")
        sys.exit(1)

    print(f"\nProfiling: {Path(args.czi_file).name}")
    print(f"Loading {args.max_tiles} tiles...\n")

    output, timings, samples = profile_sequential_loading(
        args.czi_file,
        max_tiles=args.max_tiles,
        channel=args.channel,
        scene=args.scene
    )

    print(f"Final output shape: {output.shape}")
    print(f"Data type: {output.dtype}")


if __name__ == "__main__":
    main()
