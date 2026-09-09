"""
Gather per-sample collagen quantification results (res.csv/res_all.csv, one
subdirectory per sample) into consolidated outputs: renamed per-sample copies
plus a single combined summary CSV across the whole cohort.

Works with any pipeline output directory laid out as:
    <input_dir>/<sample>/res.csv       (per-tile results)
    <input_dir>/<sample>/res_all.csv   (whole-slide summary, from tiled_overlay.py)

e.g. this project's own Snakemake output (output/Dafni_human/<sample>/...)
or an older ad-hoc run's directory structure -- any folder of per-sample
subdirectories following that same res.csv/res_all.csv convention.
"""
import argparse
import os
import shutil

import pandas as pd
from tqdm import tqdm

from pyHisto.utils import is_valid_file_or_directory


def get_args():
    parser = argparse.ArgumentParser(
        prog="result_gather",
        description="Gather per-sample res.csv/res_all.csv into consolidated outputs",
    )
    parser.add_argument(
        "-i", "--input-dir",
        dest="input_dir",
        help="Root directory containing one subdirectory per sample",
        metavar="PATH",
        type=is_valid_file_or_directory,
        required=True,
    )
    parser.add_argument(
        "-o", "--output-dir",
        dest="output_dir",
        help="Directory to write gathered outputs into (default: <input-dir>/gathered)",
        metavar="PATH",
        default=None,
    )
    parser.add_argument(
        "--no-copy-raw",
        dest="copy_raw",
        action="store_false",
        default=True,
        help="Skip copying each sample's per-tile res.csv into <output-dir>/raw/",
    )
    return parser.parse_args()


def find_samples(input_dir):
    """Subdirectories of input_dir containing a res.csv or res_all.csv, sorted by name."""
    samples = []
    for item in sorted(os.listdir(input_dir)):
        item_path = os.path.join(input_dir, item)
        if not os.path.isdir(item_path):
            continue
        if os.path.exists(os.path.join(item_path, "res.csv")) or os.path.exists(os.path.join(item_path, "res_all.csv")):
            samples.append(item)
    return samples


def gather_results(input_dir, output_dir=None, copy_raw=True):
    """
    Gather res.csv/res_all.csv from every sample subdirectory of input_dir.

    Returns a DataFrame indexed by sample name with columns "collagen (px^2)",
    "tissue (px^2)", "collagen vs tissue (%)" -- also written to
    <output_dir>/summary.csv. Samples missing res_all.csv are skipped with a
    warning (not silently dropped).
    """
    if output_dir is None:
        output_dir = os.path.join(input_dir, "gathered")
    os.makedirs(output_dir, exist_ok=True)

    samples = find_samples(input_dir)
    if not samples:
        raise ValueError(f"No sample subdirectories with res.csv/res_all.csv found under {input_dir}")

    if copy_raw:
        raw_dir = os.path.join(output_dir, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        for sample in tqdm(samples, desc="Copying per-tile res.csv"):
            src = os.path.join(input_dir, sample, "res.csv")
            if not os.path.exists(src):
                print(f"  warning: {sample} has no res.csv, skipping raw copy")
                continue
            shutil.copyfile(src, os.path.join(raw_dir, f"{sample}.csv"))

    summary_rows = {}
    for sample in tqdm(samples, desc="Gathering whole-slide summaries"):
        src = os.path.join(input_dir, sample, "res_all.csv")
        if not os.path.exists(src):
            print(f"  warning: {sample} has no res_all.csv, excluded from summary")
            continue
        summary_rows[sample] = pd.read_csv(src, index_col=0).iloc[:, 0]

    if not summary_rows:
        raise ValueError(f"No res_all.csv found for any sample under {input_dir}")

    summary = pd.DataFrame.from_dict(summary_rows, orient="index")
    summary.index.name = "sample"
    summary = summary.sort_index()
    summary.to_csv(os.path.join(output_dir, "summary.csv"))

    return summary


def main(args):
    summary = gather_results(args.input_dir, args.output_dir, copy_raw=args.copy_raw)
    print(summary)
    print(f"\nWrote combined summary for {len(summary)} sample(s) to "
          f"{os.path.join(args.output_dir or os.path.join(args.input_dir, 'gathered'), 'summary.csv')}")


if __name__ == "__main__":
    main(get_args())
