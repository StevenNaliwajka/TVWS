from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence
import numpy as np


def compute_relative_tof(meta_data: Any, signal_grid: Sequence[Sequence[Any]]) -> np.ndarray:
    """
    For each row (X = distance), average signal.tof_air across all columns (Y = instances).

    Stores result into:
        meta_data.average_relative_tof  -> shape (N, 2), columns: [distance_ft, avg_tof_air_ns]

    Notes:
      - Ignores None / NaN / inf tof_air values.
      - If a row has no valid tof_air values, avg is np.nan.
    """
    results: List[List[float]] = []

    for x, row in enumerate(signal_grid):
        if row is None or len(row) == 0:
            continue

        # Distance for this row (assumes all signals in the row share the same distance)
        first = row[0]
        dist_ft = float(getattr(first, "distance", np.nan))

        tof_vals: List[float] = []
        for y, sig in enumerate(row):
            if sig is None:
                continue

            tof_air = getattr(sig, "tof_air", None)
            if tof_air is None:
                continue

            try:
                v = float(tof_air)
            except (TypeError, ValueError):
                continue

            if np.isfinite(v):
                tof_vals.append(v)

        avg_tof_air_ns = float(np.mean(tof_vals)) if tof_vals else float("nan")
        results.append([dist_ft, avg_tof_air_ns])

    avg_relative = np.asarray(results, dtype=float)

    # Optional: keep your expected "FT, NS" style as whole numbers (but still float dtype)
    # avg_relative[:, 0] = np.round(avg_relative[:, 0])   # distance
    # avg_relative[:, 1] = np.round(avg_relative[:, 1])   # ns

    meta_data.average_relative_tof = avg_relative
    return avg_relative
