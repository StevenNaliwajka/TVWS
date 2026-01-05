# Codebase/TOF/tof_batch.py

import csv
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from Codebase.Calculations.numeric_utils import auto_min_height, pick_arrival_time_ns, safe_float
from Codebase.FileIO.hackrf_iq import load_hackrf_iq_file
from Codebase.FileIO.layout_scan import has_capture_pair_layout, load_grid_compat, scan_capture_pairs
from Codebase.Filter.filter_singal import filter_signal
from Codebase.Object.metadata_object import MetaDataObj
from Codebase.PeakDetection.Type1.detect_peaks_in_iq import detect_peaks_in_iq
from Codebase.TOF.Type3.compute_relative_tof import compute_relative_tof
from Codebase.TOF.tof_utils import call_compute_tof, extract_tof_value


def run_capture_pair_mode(metadata: Any, project_root: Path, data_dir: Path) -> None:
    """Process *_capture_1.iq (wired) and *_capture_2.iq (air) together per run and compute DeltaTOF."""
    print("[run.py] Detected capture-pair layout. Processing CAPTURE_1 (wired) + CAPTURE_2 (air) per run...")

    pairs = scan_capture_pairs(data_dir)
    if not pairs:
        print("[run.py] [WARN] No capture pairs found under Data/. Nothing to do.")
        return

    pairs = sorted(
        pairs,
        key=lambda d: (str(d.get("distance_label", "")), str(d.get("collect_dir", "")), str(d.get("run_dir", ""))),
    )

    per_run: List[Dict[str, Any]] = []
    deltas_by_distance: Dict[str, List[float]] = {}

    t0 = time.perf_counter()
    for idx, pair in enumerate(pairs, start=1):
        dist_label = pair["distance_label"]
        dist_ft = pair.get("distance_ft")
        run_dir = Path(pair["run_dir"])
        wired_path = Path(pair["wired_path"])
        air_path = Path(pair["air_path"])

        print(f"[run.py] ({idx:04d}/{len(pairs):04d}) {dist_label}/{run_dir.name}")

        wired_iq = load_hackrf_iq_file(wired_path, metadata)
        air_iq = load_hackrf_iq_file(air_path, metadata)

        try:
            wired_f = filter_signal(metadata, wired_iq)
        except Exception as e:
            wired_f = wired_iq
            print(f"[run.py]    wired filter_signal [WARN] {type(e).__name__}: {e}")

        try:
            air_f = filter_signal(metadata, air_iq)
        except Exception as e:
            air_f = air_iq
            print(f"[run.py]    air   filter_signal [WARN] {type(e).__name__}: {e}")

        wired_peaks = detect_peaks_in_iq(metadata, wired_f, "peakdetect", auto_min_height(wired_f, metadata))
        air_peaks = detect_peaks_in_iq(metadata, air_f, "peakdetect", auto_min_height(air_f, metadata))

        t_wired_ns = pick_arrival_time_ns(wired_peaks, pick="earliest")
        t_air_ns = pick_arrival_time_ns(air_peaks, pick="earliest")

        if t_wired_ns is None or t_air_ns is None:
            try:
                wmx = float(np.max(np.abs(wired_f)))
                amx = float(np.max(np.abs(air_f)))
            except Exception:
                wmx = None
                amx = None
            print(f"[run.py]    [WARN] Missing peak time(s). wired_max_mag={wmx} air_max_mag={amx}")

        delta_ns = None
        if t_wired_ns is not None and t_air_ns is not None:
            delta_ns = float(t_air_ns) - float(t_wired_ns)
            deltas_by_distance.setdefault(dist_label, []).append(delta_ns)

        per_run.append(
            {
                "distance_label": dist_label,
                "distance_ft": safe_float(dist_ft),
                "collect_dir": str(pair["collect_dir"]),
                "run_dir": str(run_dir),
                "wired_file": str(wired_path),
                "air_file": str(air_path),
                "t_wired_ns": t_wired_ns,
                "t_air_ns": t_air_ns,
                "delta_tof_ns": delta_ns,
            }
        )

        print(f"[run.py]    t_wired={t_wired_ns} ns | t_air={t_air_ns} ns | DeltaTOF={delta_ns} ns")

    per_distance_summary: List[Dict[str, Any]] = []
    print("\n[run.py] DeltaTOF summary by distance:")
    for label in sorted(deltas_by_distance.keys()):
        vals = deltas_by_distance[label]
        mean_v = statistics.fmean(vals) if vals else None
        stdev_v = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        per_distance_summary.append(
            {
                "distance_label": label,
                "n": len(vals),
                "mean_delta_tof_ns": mean_v,
                "stdev_delta_tof_ns": stdev_v,
            }
        )
        print(f"[run.py]   {label:<12} n={len(vals):<3} mean={mean_v} ns  stdev={stdev_v} ns")

    overall_summary = {
        "n_total_runs": len(per_run),
        "n_total_with_delta": sum(1 for r in per_run if r.get("delta_tof_ns") is not None),
        "mean_delta_tof_ns_all_runs": (
            statistics.fmean([r["delta_tof_ns"] for r in per_run if r.get("delta_tof_ns") is not None])
            if any(r.get("delta_tof_ns") is not None for r in per_run)
            else None
        ),
    }

    out_dir = project_root / "Outputs" / "TOF"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    json_path = out_dir / f"tof_pair_results_{ts}.json"
    csv_summary_path = out_dir / f"tof_pair_summary_{ts}.csv"
    csv_runs_path = out_dir / f"tof_pair_runs_{ts}.csv"

    payload = {
        "mode": "capture_pair",
        "timestamp_local": datetime.now().isoformat(timespec="seconds"),
        "data_dir": str(data_dir),
        "per_run": per_run,
        "per_distance_summary": per_distance_summary,
        "overall_summary": overall_summary,
    }

    print("\n[run.py] Writing output files...")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(csv_summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["distance_label", "n", "mean_delta_tof_ns", "stdev_delta_tof_ns"])
        w.writeheader()
        for row in per_distance_summary:
            w.writerow(row)

    with open(csv_runs_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "distance_label",
                "distance_ft",
                "collect_dir",
                "run_dir",
                "wired_file",
                "air_file",
                "t_wired_ns",
                "t_air_ns",
                "delta_tof_ns",
            ],
        )
        w.writeheader()
        for row in per_run:
            w.writerow(row)

    t1 = time.perf_counter()
    print(f"[run.py] [OK] Wrote JSON: {json_path}")
    print(f"[run.py] [OK] Wrote CSV : {csv_summary_path}")
    print(f"[run.py] [OK] Wrote CSV : {csv_runs_path}")
    print(f"[run.py] Done (capture-pair mode). Total runtime: {t1 - t0:.2f}s")


def _distance_label_for(row_idx: int, sig: Any, folders: Optional[List[Path]]) -> str:
    if folders and row_idx is not None and 0 <= row_idx < len(folders):
        return folders[row_idx].name
    p = getattr(sig, "path", None)
    if p:
        try:
            return Path(p).parent.name
        except Exception:
            pass
    d = getattr(sig, "distance", None)
    return f"{d}ft"


def run_grid_mode(metadata: Any, project_root: Path, data_dir: Path) -> None:
    """Legacy mode: load a grid of signals, compute TOF per signal, then compute_relative_tof()."""
    print("[run.py] Loading signal grid...")
    t_load0 = time.perf_counter()
    signal_grid, file_grid, distances, folders = load_grid_compat(data_dir)
    t_load1 = time.perf_counter()

    n_rows = len(signal_grid) if signal_grid is not None else 0
    n_total = sum(len(r) for r in signal_grid) if signal_grid else 0
    print(f"[run.py] Loaded grid: {n_rows} distance rows, {n_total} total signals ({t_load1 - t_load0:.2f}s)")

    if folders:
        print("[run.py] Distance folders (row order):")
        for i, f in enumerate(folders):
            d = distances[i] if distances and i < len(distances) else None
            n_files = len(signal_grid[i]) if i < len(signal_grid) else 0
            d_str = f"{d:.4f} ft" if isinstance(d, (int, float)) else str(d)
            print(f"  - row {i:02d}: {f.name:<12} | {d_str:<10} | {n_files} file(s)")

    # Identify wired reference (prefer folder named "Wired", otherwise distance==0, otherwise last row)
    wired_signal = None
    wired_row_idx = None

    if folders:
        for i, f in enumerate(folders):
            if f.name.strip().lower() == "wired":
                wired_row_idx = i
                break

    if wired_row_idx is None and distances:
        for i, d in enumerate(distances):
            if safe_float(d) == 0.0:
                wired_row_idx = i
                break

    if wired_row_idx is None:
        wired_row_idx = len(signal_grid) - 1

    if signal_grid and signal_grid[wired_row_idx]:
        wired_signal = signal_grid[wired_row_idx][0]

    if wired_signal is None:
        raise RuntimeError("Could not find a wired reference signal. Ensure Data/Wired contains at least one .iq file.")

    print(f"[run.py] Wired reference row index: {wired_row_idx} ({folders[wired_row_idx].name if folders else 'unknown'})")
    print(f"[run.py] Wired reference file     : {getattr(wired_signal, 'path', '')}")

    per_measurement: List[Dict[str, Any]] = []
    tof_values_by_distance: Dict[str, List[float]] = {}
    unit_by_distance: Dict[str, str] = {}

    # ---- Wired first ----
    print("\n[run.py] Processing WIRED reference...")
    t_wired0 = time.perf_counter()

    try:
        wired_iq = getattr(wired_signal, "iq", wired_signal)
        wired_filtered_iq = filter_signal(metadata, wired_iq)
        print("[run.py] Wired: filter_signal [OK]")
    except Exception as e:
        wired_filtered_iq = getattr(wired_signal, "iq", wired_signal)
        print(f"[run.py] Wired: filter_signal [WARN]  (skipped due to error: {type(e).__name__}: {e})")

    print("[run.py] Wired: detect_peaks_in_iq...")
    wired_peaks = detect_peaks_in_iq(metadata, wired_filtered_iq, "peakdetect", 4)
    print("[run.py] Wired: compute_tof...")
    wired_tof_result = call_compute_tof(metadata, wired_signal, wired_peaks)
    wired_tof_val, wired_unit = extract_tof_value(wired_tof_result, wired_signal)

    wired_label = _distance_label_for(wired_row_idx, wired_signal, folders)
    print(f"[run.py] Wired TOF = {wired_tof_val} ({wired_unit})  label={wired_label}")

    t_wired1 = time.perf_counter()
    print(f"[run.py] Wired processing time: {t_wired1 - t_wired0:.2f}s")

    per_measurement.append(
        {
            "distance_label": wired_label,
            "distance_ft": safe_float(getattr(wired_signal, "distance", 0.0)),
            "file": str(getattr(wired_signal, "path", "")),
            "tof": wired_tof_val,
            "tof_unit": wired_unit,
            "is_wired": True,
        }
    )

    # ---- Air rows ----
    print("\n[run.py] Processing AIR measurements...")
    processed = 0
    errors = 0
    t_air0 = time.perf_counter()

    for r, row in enumerate(signal_grid):
        row_label = folders[r].name if folders and r < len(folders) else f"row_{r}"
        row_dist = distances[r] if distances and r < len(distances) else None

        if r == wired_row_idx:
            print(f"[run.py] Skipping row {r:02d} ({row_label}) - wired row")
            continue

        print(f"\n[run.py] Row {r:02d} - {row_label} (distance={row_dist}) - {len(row)} file(s)")
        for c, sig in enumerate(row):
            if sig is None or sig is wired_signal:
                continue

            path = str(getattr(sig, "path", ""))
            print(f"[run.py]   [{r:02d}:{c:02d}] {Path(path).name if path else '(no path)'}")

            try:
                try:
                    iq = getattr(sig, "iq", sig)
                    filtered_iq = filter_signal(metadata, iq)
                except Exception as e:
                    filtered_iq = getattr(sig, "iq", sig)
                    print(f"[run.py]      filter_signal [WARN] (skipped: {type(e).__name__}: {e})")

                peaks = detect_peaks_in_iq(metadata, filtered_iq, "peakdetect", 4)
                tof_result = call_compute_tof(metadata, sig, peaks)
                tof_val, tof_unit = extract_tof_value(tof_result, sig)

                d_label = _distance_label_for(r, sig, folders)
                d_ft = safe_float(getattr(sig, "distance", None))

                print(f"[run.py]      TOF = {tof_val} ({tof_unit})  label={d_label}  dist_ft={d_ft}")

                per_measurement.append(
                    {
                        "distance_label": d_label,
                        "distance_ft": d_ft,
                        "file": path,
                        "tof": tof_val,
                        "tof_unit": tof_unit,
                        "is_wired": False,
                    }
                )

                if tof_val is not None:
                    tof_values_by_distance.setdefault(d_label, []).append(tof_val)
                    unit_by_distance.setdefault(d_label, tof_unit)

                processed += 1

            except Exception as e:
                errors += 1
                print(f"[run.py]      ERROR [ERROR] {type(e).__name__}: {e}")

    t_air1 = time.perf_counter()
    print(f"\n[run.py] Air processing complete: {processed} processed, {errors} errors ({t_air1 - t_air0:.2f}s)")

    # Relative TOF (existing flow)
    print("\n[run.py] Computing relative TOF across grid...")
    t_rel0 = time.perf_counter()
    compute_relative_tof(metadata, signal_grid)
    t_rel1 = time.perf_counter()
    print(f"[run.py] compute_relative_tof [OK] ({t_rel1 - t_rel0:.2f}s)")

    # Summaries
    print("\n[run.py] Building summaries...")
    per_distance_summary: List[Dict[str, Any]] = []
    all_air_tofs: List[float] = []

    if folders:
        ordered_labels = [f.name for f in folders if f.name.strip().lower() != "wired"]
        for k in tof_values_by_distance.keys():
            if k not in ordered_labels and k.strip().lower() != "wired":
                ordered_labels.append(k)
    else:
        ordered_labels = sorted([k for k in tof_values_by_distance.keys() if k.strip().lower() != "wired"])

    for label in ordered_labels:
        vals = tof_values_by_distance.get(label, [])
        if not vals:
            per_distance_summary.append(
                {
                    "distance_label": label,
                    "n": 0,
                    "mean_tof": None,
                    "stdev_tof": None,
                    "tof_unit": unit_by_distance.get(label, "unknown"),
                }
            )
            print(f"[run.py]   {label:<12} n=0  mean=None  stdev=None")
            continue

        all_air_tofs.extend(vals)
        mean_v = statistics.fmean(vals)
        stdev_v = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        unit = unit_by_distance.get(label, "unknown")

        per_distance_summary.append(
            {"distance_label": label, "n": len(vals), "mean_tof": mean_v, "stdev_tof": stdev_v, "tof_unit": unit}
        )
        print(f"[run.py]   {label:<12} n={len(vals):<3} mean={mean_v}  stdev={stdev_v}  unit={unit}")

    overall_summary = {
        "n_total_air_measurements": len(all_air_tofs),
        "mean_tof_all_air_measurements": statistics.fmean(all_air_tofs) if all_air_tofs else None,
        "mean_of_distance_means": (
            statistics.fmean([d["mean_tof"] for d in per_distance_summary if d.get("mean_tof") is not None])
            if any(d.get("mean_tof") is not None for d in per_distance_summary)
            else None
        ),
        "wired_tof": wired_tof_val,
        "wired_tof_unit": wired_unit,
    }

    print("\n[run.py] Overall summary:")
    print(f"[run.py]   Total air measurements : {overall_summary['n_total_air_measurements']}")
    print(f"[run.py]   Mean TOF (all air)     : {overall_summary['mean_tof_all_air_measurements']} (unknown)")
    print(f"[run.py]   Mean of distance means : {overall_summary['mean_of_distance_means']} (unknown)")
    print(f"[run.py]   Wired TOF              : {overall_summary['wired_tof']} ({overall_summary['wired_tof_unit']})")

    avg_rel = []
    if hasattr(metadata, "average_relative_tof"):
        try:
            for ft, ps_per_ft in metadata.average_relative_tof:
                avg_rel.append({"distance_ft": safe_float(ft), "ps_per_ft_over_air": safe_float(ps_per_ft)})
        except Exception:
            pass

    out_dir = project_root / "Outputs" / "TOF"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    json_path = out_dir / f"tof_results_{ts}.json"
    csv_path = out_dir / f"tof_summary_{ts}.csv"

    payload = {
        "timestamp_local": datetime.now().isoformat(timespec="seconds"),
        "data_dir": str(data_dir),
        "per_measurement": per_measurement,
        "per_distance_summary": per_distance_summary,
        "overall_summary": overall_summary,
        "average_relative_tof_ps_per_ft": avg_rel,
    }

    print("\n[run.py] Writing output files...")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["distance_label", "n", "mean_tof", "stdev_tof", "tof_unit"])
        w.writeheader()
        for row in per_distance_summary:
            w.writerow(row)

    print(f"[run.py] [OK] Wrote JSON: {json_path}")
    print(f"[run.py] [OK] Wrote CSV : {csv_path}")

    if hasattr(metadata, "average_relative_tof"):
        print("\n[run.py] average_relative_tof (ps per ft over air):")
        for ft, ps in metadata.average_relative_tof:
            ft_str = f"{int(round(ft))}" if np.isfinite(ft) else "?"
            ps_str = "N/A" if not np.isfinite(ps) else f"{int(round(ps)):,}"
            print(f"  - {ft_str} Ft, {ps_str} PS Per Ft Over Air")


def run_tof_batch() -> None:
    t0 = time.perf_counter()

    metadata = MetaDataObj()
    project_root = Path(__file__).resolve().parents[2]  # Codebase/TOF/tof_batch.py -> Codebase -> project root
    data_dir = project_root / "Data"

    print("=" * 72)
    print("[run.py] Starting TOF batch run")
    print(f"[run.py] Project root : {project_root}")
    print(f"[run.py] Data dir      : {data_dir}")
    print("=" * 72)

    if has_capture_pair_layout(data_dir):
        run_capture_pair_mode(metadata, project_root, data_dir)
    else:
        run_grid_mode(metadata, project_root, data_dir)

    t1 = time.perf_counter()
    print("\n" + "=" * 72)
    print(f"[run.py] Done. Total runtime: {t1 - t0:.2f}s")
    print("=" * 72 + "\n")
