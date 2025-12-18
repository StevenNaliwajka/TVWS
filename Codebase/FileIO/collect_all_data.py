## Data is located in
## Data/

## Data folders are structured like
## Data/10 Feet/.... with multiple IQ files in there.
## Data/15 Feet/....
## Data/... Feet/...
## Data/Wired/ with a single iq file.

# Codebase/Signal/load_signals_from_data.py
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from Codebase.FileIO.load_hackrf_iq import load_hackrf_iq
from Codebase.Object.signal_object import Signal


def _parse_distance_ft(folder_name: str) -> float:
    """
    Extract distance (feet) from folder name like:
      - "10 Feet"
      - "15 feet"
      - "20ft"
    Special case:
      - "Wired" => 0
    """
    name = folder_name.strip().lower()

    if name == "wired":
        return 0.0

    m = re.search(r"(\d+(?:\.\d+)?)", name)
    if not m:
        raise ValueError(
            f"Could not parse distance from folder name: '{folder_name}'. "
            "Expected something like '10 Feet' or '15ft', or 'Wired'."
        )
    return float(m.group(1))


def build_iq_file_grid(data_dir: str | Path) -> Tuple[List[List[Path]], List[float], List[Path]]:
    """
    Returns:
      file_grid: 2D list of .iq Paths (each row = one distance folder)
      distances: distance value for each row (same length as file_grid)
      folders:   folder Path for each row (same length as file_grid)

    Wired row (if present) is always last.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    groups: List[Tuple[float, Path, bool]] = []  # (distance, folder, is_wired)

    for child in data_dir.iterdir():
        if not child.is_dir():
            continue

        is_wired = child.name.strip().lower() == "wired"
        dist = _parse_distance_ft(child.name) if (is_wired or re.search(r"\d", child.name)) else None

        # Only include folders that are either Wired or have a parsable number
        if dist is None:
            continue

        groups.append((float(dist), child, is_wired))

    if not groups:
        raise ValueError(f"No distance folders found under: {data_dir}")

    # Sort non-wired by distance, then append wired last (regardless of its distance=0)
    non_wired = sorted([g for g in groups if not g[2]], key=lambda x: x[0])
    wired = [g for g in groups if g[2]]
    ordered = non_wired + wired  # wired row last

    file_grid: List[List[Path]] = []
    distances: List[float] = []
    folders: List[Path] = []

    for dist, folder, _is_wired in ordered:
        iq_files = sorted(folder.rglob("*.iq"))
        # If a folder has no .iq files, still create an empty row (keeps indexing consistent)
        file_grid.append(iq_files)
        distances.append(dist)
        folders.append(folder)

    return file_grid, distances, folders


def load_signal_grid(data_dir: str | Path) -> Tuple[List[List[Signal]], List[List[Path]], List[float], List[Path]]:
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

    return signal_grid
