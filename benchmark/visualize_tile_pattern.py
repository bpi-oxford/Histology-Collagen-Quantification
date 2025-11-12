#!/usr/bin/env python3
"""
Visualize CZI tile access patterns to understand I/O optimization potential.

This script:
1. Loads tile bounding boxes from a CZI file
2. Visualizes tile layout and different reading orders
3. Calculates seek distance for different strategies
4. Helps identify optimal reading pattern

Usage:
    python benchmark/visualize_tile_pattern.py /path/to/file.czi
"""

import sys
import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Add parent directory for pyHisto
sys.path.insert(0, str(Path(__file__).parent.parent / "dependency" / "pyHisto"))

import aicspylibczi
import pathlib


def load_tile_bboxes(czi_path, scene=0):
    """Extract tile bounding boxes from CZI file."""
    image = aicspylibczi.CziFile(pathlib.Path(czi_path))
    dims_shape = image.get_dims_shape()[0]

    # Determine channel dimension
    has_a = 'A' in dims_shape
    has_c = 'C' in dims_shape
    ch_dim = "A" if has_a else ("C" if has_c else None)

    # Get tile count
    if 'M' not in dims_shape:
        raise ValueError("No mosaic dimension 'M' found")
    total_tiles = dims_shape['M'][1]

    print(f"Found {total_tiles} tiles in CZI file")

    # Extract bounding boxes
    tile_bboxes = []
    for m_idx in range(total_tiles):
        try:
            if ch_dim == "C":
                bbox = image.get_mosaic_tile_bounding_box(M=m_idx, S=scene, C=0)
            elif ch_dim == "A":
                bbox = image.get_mosaic_tile_bounding_box(M=m_idx, S=scene, C=0)
            else:
                bbox = image.get_mosaic_tile_bounding_box(M=m_idx, S=scene)

            tile_bboxes.append({
                "idx": m_idx,
                "x": bbox.x,
                "y": bbox.y,
                "w": bbox.w,
                "h": bbox.h
            })
        except Exception as e:
            print(f"Warning: Could not get bbox for tile {m_idx}: {e}")
            continue

    try:
        image.close()
    except AttributeError:
        pass

    return tile_bboxes


def calculate_seek_distance(tile_order):
    """
    Calculate total seek distance for a given tile reading order.

    Assumes seek distance is proportional to Euclidean distance between
    tile centers (approximation of file offset distance).
    """
    total_distance = 0.0
    for i in range(len(tile_order) - 1):
        t1 = tile_order[i]
        t2 = tile_order[i + 1]

        # Center coordinates
        x1 = t1["x"] + t1["w"] / 2
        y1 = t1["y"] + t1["h"] / 2
        x2 = t2["x"] + t2["w"] / 2
        y2 = t2["y"] + t2["h"] / 2

        # Euclidean distance
        distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        total_distance += distance

    return total_distance


def visualize_tile_patterns(tile_bboxes, output_path=None):
    """Create visualization comparing different tile reading orders."""

    # Define reading strategies
    strategies = {
        "Index Order (Current)": list(tile_bboxes),
        "Spatial Y-X (Proposed)": sorted(tile_bboxes, key=lambda t: (t["y"], t["x"])),
        "Spatial X-Y": sorted(tile_bboxes, key=lambda t: (t["x"], t["y"])),
        "Random (Worst Case)": np.random.permutation(tile_bboxes).tolist()
    }

    # Calculate seek distances
    seek_distances = {
        name: calculate_seek_distance(order)
        for name, order in strategies.items()
    }

    # Normalize distances to Index Order baseline
    baseline = seek_distances["Index Order (Current)"]
    relative_distances = {
        name: dist / baseline
        for name, dist in seek_distances.items()
    }

    # Create visualization
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('CZI Tile Reading Pattern Analysis', fontsize=16, fontweight='bold')

    # Get overall bounds
    min_x = min(t["x"] for t in tile_bboxes)
    max_x = max(t["x"] + t["w"] for t in tile_bboxes)
    min_y = min(t["y"] for t in tile_bboxes)
    max_y = max(t["y"] + t["h"] for t in tile_bboxes)

    # Plot tile layout
    ax = axes[0, 0]
    for tile in tile_bboxes:
        rect = mpatches.Rectangle(
            (tile["x"], tile["y"]),
            tile["w"],
            tile["h"],
            linewidth=0.5,
            edgecolor='blue',
            facecolor='lightblue',
            alpha=0.5
        )
        ax.add_patch(rect)
        # Add tile index
        ax.text(
            tile["x"] + tile["w"] / 2,
            tile["y"] + tile["h"] / 2,
            str(tile["idx"]),
            ha='center',
            va='center',
            fontsize=6
        )

    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_aspect('equal')
    ax.set_title('Tile Layout\n(with index numbers)', fontweight='bold')
    ax.set_xlabel('X coordinate (pixels)')
    ax.set_ylabel('Y coordinate (pixels)')
    ax.invert_yaxis()  # Image coordinates

    # Plot reading order for each strategy
    strategy_axes = {
        "Index Order (Current)": axes[0, 1],
        "Spatial Y-X (Proposed)": axes[0, 2],
        "Spatial X-Y": axes[1, 0],
        "Random (Worst Case)": axes[1, 1]
    }

    for strategy_name, ax in strategy_axes.items():
        order = strategies[strategy_name]

        # Draw tiles
        for tile in tile_bboxes:
            rect = mpatches.Rectangle(
                (tile["x"], tile["y"]),
                tile["w"],
                tile["h"],
                linewidth=0.5,
                edgecolor='gray',
                facecolor='lightgray',
                alpha=0.3
            )
            ax.add_patch(rect)

        # Draw reading order path
        centers = [
            (t["x"] + t["w"] / 2, t["y"] + t["h"] / 2)
            for t in order
        ]
        xs, ys = zip(*centers)

        # Color gradient for reading order
        colors = plt.cm.viridis(np.linspace(0, 1, len(centers)))

        for i in range(len(centers) - 1):
            ax.plot(
                [xs[i], xs[i + 1]],
                [ys[i], ys[i + 1]],
                color=colors[i],
                linewidth=1,
                alpha=0.6
            )

        # Start and end markers
        ax.plot(xs[0], ys[0], 'go', markersize=8, label='Start')
        ax.plot(xs[-1], ys[-1], 'ro', markersize=8, label='End')

        ax.set_xlim(min_x, max_x)
        ax.set_ylim(min_y, max_y)
        ax.set_aspect('equal')
        ax.invert_yaxis()

        # Title with seek distance
        rel_dist = relative_distances[strategy_name]
        color = 'green' if rel_dist < 1.0 else ('red' if rel_dist > 1.0 else 'black')
        ax.set_title(
            f'{strategy_name}\nSeek Distance: {rel_dist:.2f}x baseline',
            fontweight='bold',
            color=color
        )
        ax.set_xlabel('X coordinate')
        ax.set_ylabel('Y coordinate')
        ax.legend(loc='upper right', fontsize=8)

    # Bar chart comparing seek distances
    ax = axes[1, 2]
    names = list(relative_distances.keys())
    values = list(relative_distances.values())
    colors_bar = ['red', 'green', 'orange', 'darkred']

    bars = ax.bar(range(len(names)), values, color=colors_bar, alpha=0.7)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha='right', fontsize=10)
    ax.set_ylabel('Relative Seek Distance', fontweight='bold')
    ax.set_title('Seek Distance Comparison\n(lower is better)', fontweight='bold')
    ax.axhline(y=1.0, color='black', linestyle='--', linewidth=1, label='Baseline')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f'{value:.2f}x',
            ha='center',
            va='bottom',
            fontweight='bold'
        )

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"\nVisualization saved to: {output_path}")
    else:
        plt.show()

    # Print summary
    print("\n" + "="*70)
    print("TILE ACCESS PATTERN ANALYSIS SUMMARY")
    print("="*70)
    print(f"\nTotal tiles: {len(tile_bboxes)}")
    print(f"\nSeek Distance Comparison (relative to Index Order):")
    for name, rel_dist in relative_distances.items():
        improvement = (1.0 - rel_dist) * 100
        symbol = "✓" if rel_dist < 1.0 else "✗"
        print(f"  {symbol} {name:30s}: {rel_dist:6.2f}x ({improvement:+.1f}%)")

    best_strategy = min(relative_distances, key=relative_distances.get)
    best_improvement = (1.0 - relative_distances[best_strategy]) * 100

    print(f"\nRecommendation: Use '{best_strategy}'")
    print(f"  Expected seek distance reduction: {best_improvement:.1f}%")
    print(f"  Estimated loading time improvement: {best_improvement * 0.5:.1f}% - {best_improvement * 0.8:.1f}%")
    print("  (Conservative estimate: 50-80% of seek reduction translates to time savings)")
    print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize CZI tile access patterns and optimization potential",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Visualize tile pattern
  python benchmark/visualize_tile_pattern.py input.czi

  # Save visualization to file
  python benchmark/visualize_tile_pattern.py input.czi -o tile_analysis.png

  # Analyze specific scene
  python benchmark/visualize_tile_pattern.py input.czi --scene 1
        """
    )

    parser.add_argument(
        "czi_file",
        help="Path to CZI file to analyze"
    )

    parser.add_argument(
        "--scene",
        type=int,
        default=0,
        help="Scene index (default: 0)"
    )

    parser.add_argument(
        "-o", "--output",
        help="Output path for visualization (default: display interactively)"
    )

    args = parser.parse_args()

    if not Path(args.czi_file).exists():
        print(f"Error: File not found: {args.czi_file}")
        sys.exit(1)

    print(f"\nAnalyzing tile patterns in: {Path(args.czi_file).name}")
    print(f"Scene: {args.scene}\n")

    # Load tile data
    tile_bboxes = load_tile_bboxes(args.czi_file, args.scene)

    if len(tile_bboxes) == 0:
        print("Error: No tiles found in CZI file")
        sys.exit(1)

    # Create visualization
    visualize_tile_patterns(tile_bboxes, args.output)


if __name__ == "__main__":
    main()
