"""
QC preview PNG for a decon_seg_zarr output: whole-slide overview with the
collagen overlay + 3 marked crop boxes on the left, and 1:1-pixel zoomed
crops (PSR channel + collagen overlay) of those boxes stacked on the right.

Only ever reads a coarse pyramid level (for the overview) plus small 1:1
crops (for the zoom panels) -- never the full-resolution arrays -- so this
is safe to run memory-wise regardless of the source slide's size.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
import zarr
from skimage.transform import resize
from skimage.segmentation import find_boundaries
from skimage.morphology import dilation
import matplotlib.patheffects as path_effects

from pyHisto.utils import is_valid_file_or_directory


def get_args():
    parser = argparse.ArgumentParser(prog="qc_preview",
                                      description="Render a QC preview PNG for a decon_seg_zarr output")
    parser.add_argument("-i", "--input-dir", dest="input_dir", required=True, metavar="DIR",
                         type=is_valid_file_or_directory,
                         help="Sample output directory (containing data.zarr/{raw,psr,collagen}, res.csv)")
    parser.add_argument("-o", "--output", dest="output", required=True, metavar="PATH",
                         help="Output PNG path")
    parser.add_argument("--n-crops", dest="n_crops", default=3, type=int, metavar="INT",
                         help="Number of 1:1 zoom crop regions to show (default 3)")
    parser.add_argument("--overview-level", dest="overview_level", default=None, type=int, metavar="INT",
                         help="data.zarr/raw pyramid level to use for the overview (default: coarsest)")
    parser.add_argument("--czi-path", dest="czi_path", default=None, metavar="PATH",
                         help="Path to the original source CZI, used to read physical pixel size (um) for "
                              "a real-unit scale bar. Falls back to a pixel-count scale bar if omitted.")
    parser.add_argument("--scale-bar-um", dest="scale_bar_um", default=1000.0, type=float, metavar="FLOAT",
                         help="Scale bar length in micrometers (default: 1000)")
    return parser.parse_args()


def _round_scale_bar_length(image_width, fraction=0.15):
    """Pick a visually clean round-number scale bar length (in pixels),
    roughly `fraction` of the image width -- e.g. 5000 rather than 4831."""
    target = image_width * fraction
    magnitude = 10 ** int(np.floor(np.log10(max(target, 1))))
    for mult in (1, 2, 5, 10):
        candidate = mult * magnitude
        if candidate >= target:
            return int(candidate)
    return int(10 * magnitude)


def _pick_crop_regions(res_csv_path, n_crops, min_tissue_px=1000):
    """Pick n_crops rows whose collagen fraction is closest to 50% (and with
    enough tissue to be meaningful), as (x0, y0, x1, y1) tuples in target-
    resolution pixel coordinates -- these match data.zarr/psr and data.zarr/collagen's own
    coordinate space directly since res.csv is written in that same space.

    Deliberately NOT the highest-collagen regions: those tend to be near-
    100% collagen (solid overlay, no visible boundary), which is useless for
    visually checking whether the segmentation boundary itself looks right.
    A ~50/50 mix shows both classes side by side in the same crop.
    """
    df = pd.read_csv(res_csv_path)
    df = df[df["tissue (px^2)"] >= min_tissue_px].copy()
    df["dist_from_mid"] = (df["collagen vs tissue (%)"] - 50).abs()
    df = df.sort_values("dist_from_mid").head(n_crops)
    return list(df[["x0", "y0", "x1", "y1"]].itertuples(index=False, name=None))


def main(args):
    raw_root = zarr.open_group(os.path.join(args.input_dir, "data.zarr", "raw"), mode="r")
    n_levels = len(raw_root.attrs["ome"]["multiscales"][0]["datasets"])
    overview_level = args.overview_level if args.overview_level is not None else n_levels - 1

    psr_arr = zarr.open_array(os.path.join(args.input_dir, "data.zarr", "psr"), mode="r")
    collagen_arr = zarr.open_array(os.path.join(args.input_dir, "data.zarr", "collagen"), mode="r")
    target_hw = psr_arr.shape

    overview_czyx = np.asarray(raw_root[str(overview_level)])
    overview_rgb = np.transpose(overview_czyx[:, 0, :, :], (1, 2, 0)).astype(np.float32)
    overview_hw = overview_rgb.shape[:2]

    # Per-channel percentile normalization ("auto contrast"): a single
    # global max() is fragile against a handful of outlier/hot pixels, which
    # can wash out normal tissue contrast into near-solid false color.
    for c in range(overview_rgb.shape[2]):
        lo, hi = np.percentile(overview_rgb[:, :, c], [1, 99.5])
        if hi <= lo:
            continue
        overview_rgb[:, :, c] = np.clip((overview_rgb[:, :, c] - lo) / (hi - lo), 0, 1)

    # Downsample the full-res collagen mask to EXACTLY overview_hw via a
    # coarse strided zarr read (cheap -- never materializes the full array)
    # followed by a precise resize. The strided read alone can be off by a
    # few pixels from overview_hw due to integer stride rounding, and
    # imshow()-ing two arrays of slightly different shape on the same axes
    # without a shared `extent` stretches them independently -- that's what
    # caused the vertical-stretch mismatch between the mask and base image.
    y_stride = max(1, target_hw[0] // overview_hw[0] // 2)
    x_stride = max(1, target_hw[1] // overview_hw[1] // 2)
    collagen_overview_raw = np.asarray(collagen_arr[::y_stride, ::x_stride])
    collagen_overview = resize(collagen_overview_raw.astype(bool), overview_hw,
                                order=0, anti_aliasing=False, preserve_range=True)

    crop_regions = _pick_crop_regions(os.path.join(args.input_dir, "res.csv"), args.n_crops)
    scale_y = overview_hw[0] / target_hw[0]
    scale_x = overview_hw[1] / target_hw[1]

    # Shared pixel-space extent for every imshow call on the overview axes,
    # so the base image, mask overlay, and bbox rectangles are guaranteed to
    # line up regardless of any source array's exact shape.
    extent = (0, overview_hw[1], overview_hw[0], 0)

    fig = plt.figure(figsize=(14, 4 * max(len(crop_regions), 1)))
    gs = fig.add_gridspec(max(len(crop_regions), 1), 2, width_ratios=[1.3, 1])

    ax_overview = fig.add_subplot(gs[:, 0])
    ax_overview.imshow(overview_rgb, extent=extent)
    overlay = np.zeros((*collagen_overview.shape, 4))
    overlay[collagen_overview > 0] = [1, 0, 0, 0.4]  # semi-transparent red
    ax_overview.imshow(overlay, extent=extent)
    ax_overview.set_title(f"Overview (level {overview_level}) + collagen overlay")
    ax_overview.axis("off")

    # Scale bar: physical units (um) when a source CZI is given (read via
    # pyHisto.io.get_czi_physical_pixel_size), else fall back to an honest
    # pixel-count bar. High-contrast styling (bright yellow, heavy black
    # outline) since the overview mixes both very dark and very light
    # regions -- a plain black/white line disappears against one or the
    # other; yellow-on-black-outline reads clearly against both.
    bar_label = None
    if args.czi_path is not None:
        try:
            from pyHisto.io import get_czi_physical_pixel_size
            pixel_size = get_czi_physical_pixel_size(args.czi_path)
            um_per_px_fullres = float(pixel_size.X)
            bar_px_target = args.scale_bar_um / um_per_px_fullres
            bar_label = f"{args.scale_bar_um:,.0f} um"
        except Exception as e:
            print(f"Warning: could not read physical pixel size from {args.czi_path}, "
                  f"falling back to a pixel-count scale bar: {e}")
    if bar_label is None:
        bar_px_target = _round_scale_bar_length(target_hw[1])
        bar_label = f"{bar_px_target:,.0f} px (full-res)"

    bar_px_overview = bar_px_target * scale_x
    bar_x0 = overview_hw[1] * 0.05
    bar_y0 = overview_hw[0] * 0.95
    outline_heavy = [path_effects.withStroke(linewidth=5, foreground="black")]
    line, = ax_overview.plot([bar_x0, bar_x0 + bar_px_overview], [bar_y0, bar_y0], color="yellow", linewidth=4)
    line.set_path_effects(outline_heavy)
    txt = ax_overview.text(bar_x0, bar_y0 - overview_hw[0] * 0.025, bar_label,
                            color="yellow", fontsize=11, va="bottom", weight="bold")
    txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground="black")])

    colors = plt.cm.tab10.colors
    for i, (x0, y0, x1, y1) in enumerate(crop_regions):
        color = colors[i % len(colors)]
        ax_overview.add_patch(Rectangle(
            (x0 * scale_x, y0 * scale_y), (x1 - x0) * scale_x, (y1 - y0) * scale_y,
            linewidth=1.5, edgecolor=color, facecolor="none"
        ))
        label_x = x0 * scale_x - overview_hw[1] * 0.03
        label_y = y0 * scale_y - overview_hw[0] * 0.03
        label_txt = ax_overview.annotate(
            str(i + 1), xy=(x0 * scale_x, y0 * scale_y), xytext=(label_x, label_y),
            color=color, fontsize=13, weight="bold",
            arrowprops=dict(arrowstyle="-", color=color, linewidth=1),
        )
        label_txt.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground="white")])

        ax_crop = fig.add_subplot(gs[i, 1])
        psr_crop = np.asarray(psr_arr[y0:y1, x0:x1])
        collagen_crop = np.asarray(collagen_arr[y0:y1, x0:x1])
        ax_crop.imshow(psr_crop, cmap="gray")
        # Boundary-only overlay: a solid fill hides the underlying PSR
        # texture inside collagen regions, making it hard to judge whether
        # the boundary itself tracks real structure. Outlining just the
        # segmentation edge keeps the full grayscale visible everywhere.
        boundary = find_boundaries(collagen_crop.astype(bool), mode="outer")
        boundary = dilation(boundary)  # thicken by 1px for visibility
        crop_overlay = np.zeros((*collagen_crop.shape, 4))
        crop_overlay[boundary] = [0, 1, 1, 1.0]  # cyan: visible on both dark and light background
        ax_crop.imshow(crop_overlay)
        ax_crop.set_title(f"Crop {i + 1}: ({x0},{y0})-({x1},{y1}), 1:1 px", color=color, fontsize=9)
        # Colored border matching this crop's overview bbox color, so the
        # panel is visually linked to its marker without re-reading the
        # coordinate label.
        ax_crop.set_xticks([])
        ax_crop.set_yticks([])
        for spine in ax_crop.spines.values():
            spine.set_edgecolor(color)
            spine.set_linewidth(3)
            spine.set_visible(True)

    plt.tight_layout()
    plt.savefig(args.output, dpi=150)
    print(f"Wrote QC preview to {args.output}")


if __name__ == "__main__":
    main(get_args())
