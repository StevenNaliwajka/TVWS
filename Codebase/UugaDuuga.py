import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from scipy.signal import butter, filtfilt, spectrogram, find_peaks
from Codebase.FileIO.collect_all_data import load_signal_grid

from Codebase.Object.metadata_object import MetaDataObj
from Codebase.TOF.Type3.compute_relative_tof import compute_relative_tof
from Codebase.TOF.Type4.compute_tof import compute_tof
from Codebase.process_signal import process_signal

import tkinter as tk
from tkinter import filedialog
from pathlib import Path

import argparse
import csv


'''
Current Wants:
    add file explorer functionality to remove need for copying file name
    research possible filtering techniques to improve edge detection
    make it iterable over entire data folder
    add excel output file that tracks ToF to specified folder of certain transmission distances
    automate the magnitude and cluster distance variables
    Get some sleep
'''



def parse_args_with_prompts():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=None, help="Root directory to process")
    parser.add_argument("--minimumMag", type=float, default=None, help="Min peak height threshold")
    parser.add_argument("--cluster", type=int, default=None, help="Min points to qualify as a cluster")
    parser.add_argument("--clusterWeedOutDist", type=float, default=None, help="Max spacing within a cluster")

    args = parser.parse_args()

    # Prompt if missing (keeps old behavior but interactive)
    if args.minimumMag is None:
        val = input("Enter minimumMag (default 2): ").strip()
        args.minimumMag = float(val) if val else 2.0

    if args.cluster is None:
        val = input("Enter cluster (default 7): ").strip()
        args.cluster = int(val) if val else 7

    if args.clusterWeedOutDist is None:
        val = input("Enter clusterWeedOutDist (default 3.5): ").strip()
        args.clusterWeedOutDist = float(val) if val else 3.5

    root_dir = Path(args.root) if args.root else None
    return root_dir, args.minimumMag, args.cluster, args.clusterWeedOutDist

def get_root_dir():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=None, help="Root directory to process")
    args = parser.parse_args()

    if args.root:
        return Path(args.root)
    return None

def choose_folder_gui(title="Select a folder to process"):
    root = tk.Tk()
    root.withdraw()          # hide the main tkinter window
    root.attributes("-topmost", True)  # bring dialog to front

    folder = filedialog.askdirectory(title=title)
    root.destroy()

    return Path(folder) if folder else None

def process_one_iq_file(iq_path: Path,
                        fs=20e6,
                        wn=(0.005, 0.3),
                        minimumMag=2,
                        cutoff_time=50,
                        cluster=7,
                        clusterWeedOutDist=3.5,
                        timeFilter=350,
                        timeBetweenClusters=50,
                        gap_for_edges=5):
    """
    Processes a single .iq file and returns:
      - tt, IQ_data
      - clusterLocsArray, clusterPeaksArray (red points)
      - ToFtimesArray, ToFpeaksArray (blue edge points)
      - CalcToFArray (ToF per pulse)
    """

    # --- IMPORTANT: open IQ file as BINARY ---
    raw_data = np.fromfile(iq_path, dtype=np.int8)
    if raw_data.size < 4:
        return None

    # Interleaved IQ
    I = raw_data[0::2]
    Q = raw_data[1::2]
    IQ_data = I.astype(np.float64) + 1j * Q.astype(np.float64)

    # DC offset removal
    IQ_data = IQ_data - np.mean(IQ_data)

    # Keep your original time axis definition (matches your prior code)
    tt = np.arange(1, len(IQ_data) + 1) / 20.0

    # Butter bandpass + filtfilt (MATLAB-style)
    b, a = butter(N=4, Wn=wn, btype='bandpass')
    IQ_data = filtfilt(b, a, IQ_data)

    # Peak detection on magnitude
    mag = np.abs(IQ_data)
    idx, props = find_peaks(mag, height=minimumMag)
    peaks = mag[idx]
    locs = tt[idx]

    # Ignore startup peaks
    valid = locs > cutoff_time
    locs = locs[valid]
    peaks = peaks[valid]

    # ---------- CLUSTERING (no duplicates) ----------
    clusterLocsArray = []
    clusterPeaksArray = []

    s = 0
    endDat = len(locs) - 1
    while s < endDat:
        if (locs[s + 1] - locs[s]) < clusterWeedOutDist:
            startDel = s

            clusterCount = 0
            c = s
            while c < endDat and (locs[c + 1] - locs[c]) < clusterWeedOutDist:
                clusterCount += 1
                c += 1

            if clusterCount >= cluster:
                endDel = startDel + clusterCount

                for k in range(startDel, endDel + 1):
                    if k >= len(locs):
                        break
                    if locs[k] > timeFilter:
                        break

                    clusterLocsArray.append(locs[k])
                    clusterPeaksArray.append(peaks[k])

                s = endDel + 1
                continue

        s += 1

    clusterLocsArray = np.array(clusterLocsArray)
    clusterPeaksArray = np.array(clusterPeaksArray)

    # ---------- EDGE PICKING (your blue points logic, made robust) ----------
    # Instead of fixed-size arrays (np.zeros(8)), build dynamically:
    ToFtimes = []
    ToFpeaks = []

    if len(clusterLocsArray) >= 2:
        first_idx = 0
        for i in range(len(clusterLocsArray) - 1):
            # gap indicates next pulse cluster
            if (clusterLocsArray[i + 1] - clusterLocsArray[i]) > gap_for_edges:
                last_idx = i

                # store edge points: first and last of this cluster group
                ToFtimes.extend([clusterLocsArray[first_idx], clusterLocsArray[last_idx]])
                ToFpeaks.extend([clusterPeaksArray[first_idx], clusterPeaksArray[last_idx]])

                first_idx = i + 1

        # finalize last group
        last_idx = len(clusterLocsArray) - 1
        ToFtimes.extend([clusterLocsArray[first_idx], clusterLocsArray[last_idx]])
        ToFpeaks.extend([clusterPeaksArray[first_idx], clusterPeaksArray[last_idx]])

    ToFtimesArray = np.array(ToFtimes)
    ToFpeaksArray = np.array(ToFpeaks)

    # ---------- ToF calculations (pairwise differences) ----------
    CalcToF = []
    for i in range(0, len(ToFtimesArray) - 1, 2):
        CalcToF.append(ToFtimesArray[i + 1] - ToFtimesArray[i])
    CalcToFArray = np.array(CalcToF)

    return {
        "tt": tt,
        "IQ_data": IQ_data,
        "clusterLocsArray": clusterLocsArray,
        "clusterPeaksArray": clusterPeaksArray,
        "ToFtimesArray": ToFtimesArray,
        "ToFpeaksArray": ToFpeaksArray,
        "CalcToFArray": CalcToFArray,
    }


def save_plot(out, iq_path: Path):
    tt = out["tt"]
    IQ_data = out["IQ_data"]
    clusterLocsArray = out["clusterLocsArray"]
    clusterPeaksArray = out["clusterPeaksArray"]
    ToFtimesArray = out["ToFtimesArray"]
    ToFpeaksArray = out["ToFpeaksArray"]

    plt.figure(figsize=(10, 5))

    plt.plot(tt, np.abs(IQ_data), label="Magnitude")
    plt.plot(tt, np.imag(IQ_data), label="Imaginary")

    # Detected peaks (red)
    if len(clusterLocsArray) > 0:
        plt.plot(clusterLocsArray, clusterPeaksArray, 'ro', markersize=6, label="Detected Peaks")

    # Edge peaks (blue)
    if len(ToFtimesArray) > 0:
        plt.plot(ToFtimesArray, ToFpeaksArray, 'bo', markersize=6, label="Edge Peaks")

    plt.xlabel("Time")
    plt.ylabel("Magnitude")
    plt.title(iq_path.name)
    plt.grid(True, which="both", linestyle="--", alpha=0.4)
    plt.minorticks_on()
    plt.legend()
    plt.tight_layout()

    out_png = iq_path.parent / f"{iq_path.stem}_plot.png"
    plt.savefig(out_png, dpi=200)
    plt.close()
    return out_png


def save_tof_txt(out, iq_path: Path):
    CalcToFArray = out["CalcToFArray"]

    out_txt = iq_path.parent / f"{iq_path.stem}_tof.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"File: {iq_path}\n")
        f.write(f"Num ToF pulses: {len(CalcToFArray)}\n\n")
        for i, tof in enumerate(CalcToFArray, start=1):
            f.write(f"The time of flight for signal {i} is {tof}\n")
    return out_txt

def load_existing_rows(csv_path: Path):
    rows = {}  # key: (Folder, Capture, Pulse) -> ToF
    if csv_path.exists():
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                key = (r["Folder"], int(r["Capture"]), int(r["Pulse"]))
                rows[key] = float(r["ToF"])
    return rows

def upsert_tofs(rows_dict, run_name, capture_num, tof_array):
    for pulse_idx, tof in enumerate(tof_array, start=1):
        key = (run_name, int(capture_num), int(pulse_idx))
        rows_dict[key] = float(tof)  # replace if exists, add if not

def write_rows_atomic(csv_path: Path, rows_dict):
    tmp_path = csv_path.with_suffix(".tmp")
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Folder", "Capture", "Pulse", "ToF"])

        # stable output ordering
        for (folder, cap, pulse) in sorted(rows_dict.keys()):
            writer.writerow([folder, cap, pulse, rows_dict[(folder, cap, pulse)]])

    tmp_path.replace(csv_path)  # atomic-ish replace on Windows

def infer_run_name(iq_path: Path) -> str:
    # Find the nearest parent folder that looks like run_#### (robust)
    for p in iq_path.parents:
        if p.name.lower().startswith("run_"):
            return p.name
    return iq_path.parent.name  # fallback

def infer_capture_num(iq_path: Path) -> int:
    # Parses "..._capture_1.iq" safely (avoids grabbing things like 0897)
    tokens = iq_path.stem.split("_")
    for i, tok in enumerate(tokens[:-1]):
        if tok.lower() == "capture" and tokens[i + 1].isdigit():
            return int(tokens[i + 1])
    return 1  # fallback

def bulk_run(root_dir: Path, minimumMag: float, cluster: int, clusterWeedOutDist: float):
    if root_dir is None:
        print("No folder selected. Exiting.")
        return

    ROOT_DIR = Path(root_dir)

    CSV_PATH = ROOT_DIR / "tof_results.csv"
    rows = load_existing_rows(CSV_PATH)  # existing upsert map (Folder,Capture,Pulse)->ToF

    iq_files = sorted(ROOT_DIR.rglob("*.iq"))
    print(f"Selected folder: {ROOT_DIR}")
    print(f"Found {len(iq_files)} .iq files")

    for iq_path in iq_files:
        out = process_one_iq_file(
            iq_path,
            minimumMag=minimumMag,
            cluster=cluster,
            clusterWeedOutDist=clusterWeedOutDist
        )
        if out is None:
            print(f"[SKIP] {iq_path} (empty/too small)")
            continue

        run_name = infer_run_name(iq_path)
        capture_num = infer_capture_num(iq_path)

        # Optional guard: only allow capture 1/2 (prevents weird 4-digit capture IDs)
        # If you sometimes have capture_3 etc, expand this tuple.
        if capture_num not in (1, 2):
            print(f"[WARN] capture_num={capture_num} (unexpected) for {iq_path.name} -> skipping CSV write")
        else:
            # ✅ ONE source of truth for CSV writing (upsert then rewrite)
            upsert_tofs(rows, run_name, capture_num, out["CalcToFArray"])
            write_rows_atomic(CSV_PATH, rows)

        # Console output
        for i, tof in enumerate(out["CalcToFArray"], start=1):
            print(f"{iq_path.name}: The time of flight for signal {i} is {tof}")

        # Save plot + txt INSIDE the same folder as the iq file (once)
        png_path = save_plot(out, iq_path)
        txt_path = save_tof_txt(out, iq_path)
        print(f"[OK] {iq_path.name} -> {txt_path.name}, {png_path.name}")

    print(f"\nDone. CSV: {CSV_PATH}")

if __name__ == "__main__":
    root_dir, minimumMag, cluster, clusterWeedOutDist = parse_args_with_prompts()

    if root_dir is None:
        root_dir = choose_folder_gui("Pick the folder to iterate over (.iq bulk folder)")
        if root_dir is None:
            print("No folder selected. Exiting.")
            raise SystemExit(1)

    bulk_run(root_dir, minimumMag, cluster, clusterWeedOutDist)
