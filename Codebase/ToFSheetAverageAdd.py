import csv
from pathlib import Path
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

def choose_folder_gui(title="Select folder containing the CSV files"):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title=title)
    root.destroy()
    return Path(folder) if folder else None


def read_csv_rows(csv_path: Path):
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def write_side_by_side_csv(left_rows, right_rows, out_path: Path, gap_cols: int = 2):
    left_width = max((len(r) for r in left_rows), default=0)
    right_width = max((len(r) for r in right_rows), default=0)

    total_rows = max(len(left_rows), len(right_rows))
    gap = [""] * gap_cols

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        for i in range(total_rows):
            lrow = left_rows[i] if i < len(left_rows) else []
            rrow = right_rows[i] if i < len(right_rows) else []

            # pad each side so the right table starts at a fixed offset
            lpad = lrow + [""] * (left_width - len(lrow))
            rpad = rrow + [""] * (right_width - len(rrow))

            w.writerow(lpad + gap + rpad)


def main():
    root_dir = get_root_dir()
    if root_dir is None:
        root_dir = choose_folder_gui("Pick folder containing tof_results.csv and tof_averages_by_run.csv")

    left_csv = root_dir / "tof_results.csv"
    right_csv = root_dir / "tof_averages_by_run.csv"

    if not left_csv.exists():
        print(f"Missing: {left_csv}")
        return
    if not right_csv.exists():
        print(f"Missing: {right_csv}")
        return

    left_rows = read_csv_rows(left_csv)
    right_rows = read_csv_rows(right_csv)

    out_csv = root_dir / "tof_results__SIDE_BY_SIDE__tof_averages.csv"
    write_side_by_side_csv(left_rows, right_rows, out_csv, gap_cols=2)

    print(f"Left : {left_csv}")
    print(f"Right: {right_csv}")
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":


    main()
