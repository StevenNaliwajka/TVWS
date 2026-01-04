import csv
from pathlib import Path
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog
import argparse

def get_root_dir():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=None, help="Root directory to process")
    args = parser.parse_args()

    if args.root:
        return Path(args.root)
    return None

def choose_folder_gui(title="Select folder containing tof_results.csv"):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title=title)
    root.destroy()
    return Path(folder) if folder else None


def compute_averages(input_csv: Path, output_csv: Path):
    # Per-folder per-capture
    sums = defaultdict(float)
    counts = defaultdict(int)

    # Per-folder overall
    overall_sums = defaultdict(float)
    overall_counts = defaultdict(int)

    # Global (across ALL folders)
    global_sum_cap = defaultdict(float)   # capture -> sum
    global_cnt_cap = defaultdict(int)     # capture -> count
    global_sum_all = 0.0
    global_cnt_all = 0

    with open(input_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = {"Folder", "Capture", "Pulse", "ToF"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV must have columns: {sorted(required)}. Found: {reader.fieldnames}")

        for row in reader:
            folder = row["Folder"].strip()

            try:
                capture = int(row["Capture"])
                tof = float(row["ToF"])
            except Exception:
                continue

            # Only use capture 1 and 2
            if capture not in (1, 2):
                continue

            # per-folder per-capture
            sums[(folder, capture)] += tof
            counts[(folder, capture)] += 1

            # per-folder overall
            overall_sums[folder] += tof
            overall_counts[folder] += 1

            # global
            global_sum_cap[capture] += tof
            global_cnt_cap[capture] += 1
            global_sum_all += tof
            global_cnt_all += 1

    # Compute global averages
    global_avg1 = (global_sum_cap[1] / global_cnt_cap[1]) if global_cnt_cap[1] else ""
    global_avg2 = (global_sum_cap[2] / global_cnt_cap[2]) if global_cnt_cap[2] else ""
    global_avg_all = (global_sum_all / global_cnt_all) if global_cnt_all else ""

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # --- Top-of-sheet single-value block (rows 1–2) ---
        writer.writerow(["Global_Cap1_AvgToF", global_avg1,
                         "Global_Cap2_AvgToF", global_avg2,
                         "Global_Overall_AvgToF", global_avg_all])
        writer.writerow([])  # blank row

        # --- Main per-folder table ---
        writer.writerow([
            "Folder",
            "Capture1_AvgToF", "Capture1_N",
            "Capture2_AvgToF", "Capture2_N",
            "Overall_AvgToF",  "Overall_N"
        ])

        for folder in sorted(overall_counts.keys()):
            n1 = counts.get((folder, 1), 0)
            n2 = counts.get((folder, 2), 0)
            n_all = overall_counts.get(folder, 0)

            avg1 = (sums[(folder, 1)] / n1) if n1 else ""
            avg2 = (sums[(folder, 2)] / n2) if n2 else ""
            avg_all = (overall_sums[folder] / n_all) if n_all else ""

            writer.writerow([folder, avg1, n1, avg2, n2, avg_all, n_all])

    print(f"Read:  {input_csv}")
    print(f"Wrote: {output_csv}")


def main():
    root_dir = get_root_dir()
    if root_dir is None:
        root_dir = choose_folder_gui("Pick folder that contains tof_results.csv")

    input_csv = root_dir / "tof_results.csv"
    if not input_csv.exists():
        print(f"Couldn't find tof_results.csv in:\n  {folder}")
        return

    output_csv = root_dir / "tof_averages_by_run.csv"
    compute_averages(input_csv, output_csv)


if __name__ == "__main__":


    main()
