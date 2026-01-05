# Codebase/FileIO/layout_scan.py

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Codebase.FileIO.collect_all_data import load_signal_grid


def load_grid_compat(data_dir: Path):
    """
    Your collect_all_data.load_signal_grid has existed in 2 forms:
      (A) returns just signal_grid
      (B) returns (signal_grid, file_grid, distances, folders)

    This helper supports both.
    """
    out = load_signal_grid(data_dir)
    if isinstance(out, tuple) and len(out) == 4:
        return out  # signal_grid, file_grid, distances, folders
    return out, None, None, None


def parse_distance_folder_to_ft(name: str) -> Optional[float]:
    """Parse folder names like '5Ft', '7In', 'Wired' into feet when possible."""
    n = (name or "").strip().lower()
    if n == "wired":
        return 0.0
    m = re.match(r"^(\d+(?:\.\d+)?)\s*ft$", n)
    if m:
        return float(m.group(1))
    m = re.match(r"^(\d+(?:\.\d+)?)\s*in$", n)
    if m:
        return float(m.group(1)) / 12.0
    return None


def has_capture_pair_layout(data_dir: Path) -> bool:
    """Detects the new layout: Data/<Dist>/collect_*/run_*/..._capture_{1,2}.iq"""
    try:
        return any(data_dir.glob("*/collect_*/run_*/*_capture_1.iq"))
    except Exception:
        return False


def scan_capture_pairs(data_dir: Path) -> List[Dict[str, Any]]:
    """Return a flat list of capture pairs found under data_dir."""
    pairs: List[Dict[str, Any]] = []
    if not data_dir.exists():
        return pairs

    for dist_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()]):
        dist_label = dist_dir.name
        dist_ft = parse_distance_folder_to_ft(dist_label)

        for collect_dir in sorted(dist_dir.glob("collect_*")):
            for run_dir in sorted(collect_dir.glob("run_*")):
                cap1 = sorted(run_dir.glob("*_capture_1.iq"))
                cap2 = sorted(run_dir.glob("*_capture_2.iq"))
                if not cap1 or not cap2:
                    continue

                pairs.append(
                    {
                        "distance_label": dist_label,
                        "distance_ft": dist_ft,
                        "distance_dir": dist_dir,
                        "collect_dir": collect_dir,
                        "run_dir": run_dir,
                        "wired_path": cap1[0],
                        "air_path": cap2[0],
                    }
                )
    return pairs
