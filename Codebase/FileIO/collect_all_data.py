## Data is located in:
##   Data/
##
## Data folders can be structured like:
##   Data/10 Feet/....    (multiple IQ files)
##   Data/5Ft/....
##   Data/7In/....
##   Data/Wired/....      (wired baseline)
##
## This module builds a 2D "grid" of IQ files grouped by distance folder,
## converts folder names into a distance in FEET, and optionally loads each file
## into a Signal object.

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from Codebase.FileIO.load_hackrf_iq import load_hackrf_iq
from Codebase.Object.signal_object import Signal


_FEET_PER_INCH = 1.0 / 12.0


def _parse_distance_ft(folder_name: str) -> float:
    """
    Extract distance (feet) from a folder name.

    Supported examples:
      - "10 Feet" / "15 feet"
      - "20ft" / "5Ft" / "10 FT"
      - "7In" / "7 in" / "7 inches"  (converted to feet)
      - "Wired"                      (returns 0.0; handled specially in ordering)

    If a number is present but no unit is detected, we assume **feet**.
    """
    name = folder_name.strip().lower()

    # Special-case wired baseline (no distance).
    if name == "wired":
        return 0.0

    # Inches (e.g., 7In, 7 in, 7 inches)
    m_in = re.search(r"(\d+(?:\.\d+)?)\s*(in|inch|inches)\b", name)
    if m_in:
        inches = float(m_in.group(1))
        return inches * _FEET_PER_INCH

    # Feet (e.g., 5Ft, 10 feet, 20ft)
    m_ft = re.search(r"(\d+(?:\.\d+)?)\s*(ft|feet|foot)\b", name)
    if m_ft:
        return float(m_ft.group(1))

    # Fallback: if there's any number, assume feet
    m_any = re.search(r"(\d+(?:\.\d+)?)", name)
    if not m_any:
        raise ValueError(
            f"Could not parse distance from folder name: '{folder_name}'. "
            "Expected e.g. '10 Feet', '5Ft', '7In', or 'Wired'."
        )
    return float(m_any.group(1))


def build_iq_file_grid(data_dir: str | Path) -> Tuple[List[List[Path]], List[float], List[Path]]:
    """
    Returns:
      file_grid: 2D list of .iq Paths (each row = one distance folder)
      distances: distance value (feet) for each row (same length as file_grid)
      folders:   folder Path for each row (same length as file_grid)

    Notes:
      - All non-wired folders are sorted by numeric distance (in feet).
      - "Wired" (if present) is always placed last.
      - Each row contains all *.iq files under that distance folder (recursive).
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    groups: List[Tuple[float, Path, bool]] = []  # (distance_ft, folder, is_wired)

    for child in data_dir.iterdir():
        if not child.is_dir():
            continue

        is_wired = child.name.strip().lower() == "wired"

        # Only include folders that are either Wired or have a parsable number/unit.
        try:
            dist = _parse_distance_ft(child.name) if (is_wired or re.search(r"\d", child.name)) else None
        except ValueError:
            dist = None

        if dist is None:
            continue

        groups.append((float(dist), child, is_wired))

    if not groups:
        raise ValueError(f"No distance folders found under: {data_dir}")

    # Sort non-wired by distance, then append wired last (regardless of its numeric distance).
    non_wired = sorted([g for g in groups if not g[2]], key=lambda x: x[0])
    wired = [g for g in groups if g[2]]
    ordered = non_wired + wired

    file_grid: List[List[Path]] = []
    distances: List[float] = []
    folders: List[Path] = []

    for dist, folder, _is_wired in ordered:
        # Case-insensitive *.iq gather
        iq_files = sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".iq"])
        file_grid.append(iq_files)
        distances.append(dist)
        folders.append(folder)

    return file_grid, distances, folders


def load_signal_grid(
    data_dir: str | Path,
) -> Tuple[List[List[Signal]], List[List[Path]], List[float], List[Path]]:
    """
    Builds the file grid and then loads each .iq file into a Signal object.

    Returns:
      signal_grid: 2D list of Signal objects (same shape as file_grid)
      file_grid:   2D list of Paths (same shape as signal_grid)
      distances:   per-row distance (feet)
      folders:     per-row folder path
    """
    file_grid, distances, folders = build_iq_file_grid(data_dir)

    signal_grid: List[List[Signal]] = []
    for row_files, dist in zip(file_grid, distances):
        row_signals: List[Signal] = []
        for iq_path in row_files:
            iq = load_hackrf_iq(str(iq_path))
            row_signals.append(Signal(iq=iq, distance=dist, path=iq_path))
        signal_grid.append(row_signals)

    return signal_grid, file_grid, distances, folders
