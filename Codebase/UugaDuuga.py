import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from scipy.signal import butter, filtfilt, spectrogram, find_peaks
from Codebase.FileIO.collect_all_data import load_signal_grid

from Codebase.Filter.filter_singal import filter_signal

from Codebase.Object.metadata_object import MetaDataObj
from Codebase.TOF.Type3.compute_relative_tof import compute_relative_tof
from Codebase.TOF.Type4.compute_tof import compute_tof
from Codebase.process_signal import process_signal

import tkinter as tk
from tkinter import filedialog
from pathlib import Path

import argparse
import csv

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from collections import defaultdict

'''
Current Wants:
    add file explorer functionality to remove need for copying file name
    research possible filtering techniques to improve edge detection
    make it iterable over entire data folder
    add excel output file that tracks ToF to specified folder of certain transmission distances
    automate the magnitude and cluster distance variables
    Get some sleep
'''

def build_reference_centers(centers_rows, capture_num: int):
    """
    Build reference pulse center times for a given capture using median per pulse index.
    centers_rows items: (Folder, Capture, Pulse, CenterTime, FileName)
    Returns np.array ref centers indexed by pulse-1.
    """
    by_pulse = defaultdict(list)
    for folder, cap, pulse, center_t, fname in centers_rows:
        if int(cap) != int(capture_num):
            continue
        by_pulse[int(pulse)].append(float(center_t))

    if not by_pulse:
        return np.array([])

    K = max(by_pulse.keys())
    ref = []
    for p in range(1, K + 1):
        vals = by_pulse.get(p, [])
        ref.append(float(np.median(vals)) if vals else np.nan)
    return np.array(ref, dtype=float)


def align_centers_to_reference(detected_centers, ref_centers, tol):
    """
    Nearest-neighbor, one-to-one assignment of detected centers to reference centers
    with max allowed time difference `tol`.
    Returns aligned array len(ref_centers) with np.nan where missing.
    """
    detected = np.asarray(detected_centers, dtype=float)
    ref = np.asarray(ref_centers, dtype=float)

    aligned = np.full(len(ref), np.nan, dtype=float)
    used_ref = set()

    valid_ref_idx = [i for i in range(len(ref)) if np.isfinite(ref[i])]
    if not valid_ref_idx:
        return aligned

    for c in detected:
        if not np.isfinite(c):
            continue

        best_i = None
        best_d = None
        for i in valid_ref_idx:
            if i in used_ref:
                continue
            d = abs(c - ref[i])
            if best_d is None or d < best_d:
                best_d = d
                best_i = i

        if best_i is not None and best_d is not None and best_d <= tol:
            aligned[best_i] = c
            used_ref.add(best_i)

    return aligned


def compute_overall_avg_centers_with_gating(centers_rows, tol=15.0):
    """
    Align each run's detected pulse centers to a reference (per capture)
    so missing pulses don't shift indexing.
    Returns:
      matched[(cap, pulse_idx)] -> list of center times matched to that pulse
      ref1, ref2 reference arrays for capture 1 and 2
    """
    ref1 = build_reference_centers(centers_rows, capture_num=1)
    ref2 = build_reference_centers(centers_rows, capture_num=2)

    per_test = defaultdict(list)  # (folder, cap) -> list of (pulse_idx, center_time)
    for folder, cap, pulse, center_t, fname in centers_rows:
        per_test[(folder, int(cap))].append((int(pulse), float(center_t)))

    matched = defaultdict(list)

    for (folder, cap), items in per_test.items():
        items.sort(key=lambda x: x[0])
        detected_centers = [c for _, c in items]

        ref = ref1 if cap == 1 else ref2
        if ref.size == 0:
            continue

        aligned = align_centers_to_reference(detected_centers, ref, tol=tol)

        for i, c in enumerate(aligned, start=1):
            if np.isfinite(c):
                matched[(cap, i)].append(float(c))

    return matched, ref1, ref2

def parse_args_with_prompts():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=None, help="Root directory to process")
    parser.add_argument("--minMag_cap1", type=float, default=None, help="Min peak height threshold for cap1")
    parser.add_argument("--minMag_cap2", type=float, default=None, help="Min peak height threshold for cap2")
    parser.add_argument("--cluster", type=int, default=None, help="Min points to qualify as a cluster")
    parser.add_argument("--clusterWeedOutDist", type=float, default=None, help="Max spacing within a cluster")


    args = parser.parse_args()

    # Prompt if missing (keeps old behavior but interactive)
    if args.minMag_cap1 is None:
        val = input("Enter minimumMag1 (default 2): ").strip()
        args.minMag_cap1 = float(val) if val else 2.0

    if args.minMag_cap2 is None:
        val = input("Enter minimumMag2 (default 2): ").strip()
        args.minMag_cap2 = float(val) if val else 2.0

    if args.cluster is None:
        val = input("Enter cluster (default 7): ").strip()
        args.cluster = int(val) if val else 7

    if args.clusterWeedOutDist is None:
        val = input("Enter clusterWeedOutDist (default 3.5): ").strip()
        args.clusterWeedOutDist = float(val) if val else 3.5

    root_dir = Path(args.root) if args.root else None


    return root_dir, args.minMag_cap1, args.minMag_cap2, args.cluster, args.clusterWeedOutDist

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
    metadata = MetaDataObj()
    # Butter bandpass + filtfilt (MATLAB-style)
    b, a = butter(N=4, Wn=wn, btype='bandpass')
    IQ_data = filtfilt(b, a, IQ_data)
    IQ_data = filter_signal(metadata,IQ_data)

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

    pulseCentersArray = pulse_centers_from_clustered_peaks(
        clusterLocsArray,
        clusterPeaksArray,
        timeBetweenClusters=timeBetweenClusters,
        weighted=True
    )

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
        "pulseCentersArray": pulseCentersArray,
    }

def pulse_centers_from_clustered_peaks(clusterLocsArray,
                                       clusterPeaksArray,
                                       timeBetweenClusters=50,
                                       weighted=True):
    """
    Groups clustered peaks into pulses using timeBetweenClusters gap.
    Returns one center time per pulse.
    """
    locs = np.asarray(clusterLocsArray)
    peaks = np.asarray(clusterPeaksArray)

    if locs.size == 0:
        return np.array([])

    centers = []
    start = 0

    for i in range(locs.size - 1):
        if (locs[i + 1] - locs[i]) > timeBetweenClusters:
            end = i
            seg_locs = locs[start:end + 1]
            seg_peaks = peaks[start:end + 1]

            if weighted and np.sum(seg_peaks) > 0:
                center = float(np.sum(seg_locs * seg_peaks) / np.sum(seg_peaks))
            else:
                center = float(np.mean(seg_locs))

            centers.append(center)
            start = i + 1

    # finalize last group
    end = locs.size - 1
    seg_locs = locs[start:end + 1]
    seg_peaks = peaks[start:end + 1]

    if weighted and np.sum(seg_peaks) > 0:
        center = float(np.sum(seg_locs * seg_peaks) / np.sum(seg_peaks))
    else:
        center = float(np.mean(seg_locs))

    centers.append(center)
    return np.array(centers, dtype=float)

def compute_overall_avg_centers_with_baseline(centers_rows, baseline_ref, tol=15.0):
    """
    Align every run's detected pulse centers to a fixed baseline reference.
    Prevents pulse index shifting when a pulse is missed.
    """
    per_test = defaultdict(list)  # (folder, cap) -> list of (pulse_idx, center_time)
    for folder, cap, pulse, center_t, fname in centers_rows:
        per_test[(folder, int(cap))].append((int(pulse), float(center_t)))

    matched = defaultdict(list)   # (cap, pulse_idx) -> list of matched center times

    for (folder, cap), items in per_test.items():
        items.sort(key=lambda x: x[0])
        detected_centers = [c for _, c in items]

        aligned = align_centers_to_reference(detected_centers, baseline_ref, tol=tol)

        for i, c in enumerate(aligned, start=1):
            if np.isfinite(c):
                matched[(cap, i)].append(float(c))

    return matched


def write_pulse_centers_excel(xlsx_path: Path, centers_rows):
    """
    centers_rows: list of tuples (Folder, Capture, Pulse, CenterTime, FileName)
    Creates a workbook with:
      Sheet1: Per Test Pulse Centers
      Sheet2: Overall Average Pulse Centers (by Pulse #)
    """
    wb = Workbook()
    BASELINE_C2 = np.array([
        58.50642884,
        119.6756707,
        180.8778875,
        242.1766518
    ], dtype=float)
    # ---------------- Sheet 1: per test ----------------
    ws1 = wb.active
    ws1.title = "Per Test Pulse Centers"

    headers1 = ["Folder", "Capture", "Pulse", "CenterTime", "File"]
    ws1.append(headers1)
    for c in range(1, len(headers1) + 1):
        ws1.cell(row=1, column=c).font = Font(bold=True)

    for row in sorted(centers_rows, key=lambda x: (x[0], x[1], x[2], x[4])):
        ws1.append(list(row))

    ws1.freeze_panes = "A2"

    # autosize columns (basic)
    for col in range(1, len(headers1) + 1):
        max_len = 10
        for r in range(1, ws1.max_row + 1):
            v = ws1.cell(row=r, column=col).value
            if v is None:
                continue
            max_len = max(max_len, len(str(v)))
        ws1.column_dimensions[get_column_letter(col)].width = min(max_len + 2, 60)

    # ---------------- Sheet 2: overall averages ----------------
    ws2 = wb.create_sheet("Overall Avg Pulse Centers")

    headers2 = ["Capture", "Pulse", "AvgCenterTime", "N", "ReferenceCenter", "ToleranceUsed"]
    ws2.append(headers2)
    for c in range(1, len(headers2) + 1):
        ws2.cell(row=1, column=c).font = Font(bold=True)

    TOL = 15.0
    matched = compute_overall_avg_centers_with_baseline(centers_rows, BASELINE_C2, tol=TOL)

    for cap in (1, 2):
        for pulse_idx in range(1, len(BASELINE_C2) + 1):
            vals = matched.get((cap, pulse_idx), [])
            avg = float(np.mean(vals)) if vals else ""
            n = len(vals)
            ws2.append([cap, pulse_idx, avg, n, float(BASELINE_C2[pulse_idx - 1]), TOL])

    ws2.freeze_panes = "A2"
    ws2.column_dimensions["A"].width = 10
    ws2.column_dimensions["B"].width = 10
    ws2.column_dimensions["C"].width = 18
    ws2.column_dimensions["D"].width = 8
    ws2.column_dimensions["E"].width = 18
    ws2.column_dimensions["F"].width = 14
    wb.save(xlsx_path)

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

def bulk_run(root_dir: Path, minMag_cap1, minMag_cap2, cluster, clusterWeedOutDist):
    if root_dir is None:
        print("No folder selected. Exiting.")
        return

    ROOT_DIR = Path(root_dir)
    centers_rows = []  # (Folder, Capture, Pulse, CenterTime, FileName)

    CSV_PATH = ROOT_DIR / "tof_results.csv"
    rows = load_existing_rows(CSV_PATH)  # existing upsert map (Folder,Capture,Pulse)->ToF

    iq_files = sorted(ROOT_DIR.rglob("*.iq"))
    print(f"Selected folder: {ROOT_DIR}")
    print(f"Found {len(iq_files)} .iq files")

    for iq_path in iq_files:
        run_name = infer_run_name(iq_path)
        capture_num = infer_capture_num(iq_path)

        if capture_num == 1:
            minimumMag = minMag_cap1
        elif capture_num == 2:
            minimumMag = minMag_cap2
        else:
            minimumMag = minMag_cap1  # fallback (or skip)



        out = process_one_iq_file(
            iq_path,
            minimumMag=minimumMag,
            cluster=cluster,
            clusterWeedOutDist=clusterWeedOutDist
        )
        if out is None:
            print(f"[SKIP] {iq_path} (empty/too small)")
            continue

        centers = out.get("pulseCentersArray", np.array([]))
        for pulse_idx, center_t in enumerate(centers, start=1):
            centers_rows.append((run_name, int(capture_num), int(pulse_idx), float(center_t), iq_path.name))

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
    xlsx_path = ROOT_DIR / "pulse_center_times.xlsx"
    write_pulse_centers_excel(xlsx_path, centers_rows)
    print(f"[OK] Wrote pulse centers Excel: {xlsx_path}")

    print(f"\nDone. CSV: {CSV_PATH}")

if __name__ == "__main__":
    root_dir, minMag_cap1, minMag_cap2, cluster, clusterWeedOutDist = parse_args_with_prompts()




    if root_dir is None:
        root_dir = choose_folder_gui("Pick the folder to iterate over (.iq bulk folder)")
        if root_dir is None:
            print("No folder selected. Exiting.")
            raise SystemExit(1)

    bulk_run(root_dir, minMag_cap1, minMag_cap2, cluster, clusterWeedOutDist)
