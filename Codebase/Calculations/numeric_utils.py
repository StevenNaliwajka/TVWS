# Codebase/Calculations/numeric_utils.py

import math
from typing import Any, Optional

import numpy as np


def safe_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return None


def auto_min_height(iq: np.ndarray, meta: Any) -> Optional[float]:
    """Compute a reasonable amplitude threshold for peak picking.

    Uses a robust noise estimate from magnitude (median + 6*sigma_robust).
    If user provides meta.peak_min_height or meta.min_peak_height, that wins.
    """
    # user override
    for attr in ("peak_min_height", "min_peak_height"):
        v = getattr(meta, attr, None)
        try:
            if v is not None and float(v) > 0:
                return float(v)
        except Exception:
            pass

    try:
        mag = np.abs(iq).astype(np.float64)
        if mag.size == 0:
            return None

        med = float(np.median(mag))
        mad = float(np.median(np.abs(mag - med)))
        sigma = 1.4826 * mad  # robust std estimate
        thr = med + 6.0 * sigma

        # If noise is extremely low (e.g., constant), fall back to percentile
        if not math.isfinite(thr) or thr <= 0:
            thr = float(np.percentile(mag, 99.5))

        # Don't set threshold above max magnitude
        mx = float(np.max(mag))
        if thr >= mx:
            # allow peaks by disabling threshold
            return None

        return thr
    except Exception:
        return None


def pick_arrival_time_ns(peaks_df: Any, pick: str = "earliest") -> Optional[float]:
    """Choose a single arrival time from detect_peaks_in_iq() output."""
    try:
        if peaks_df is None or len(peaks_df) == 0:
            return None

        # expected columns from detect_peaks_in_iq: time_ns, amplitude
        t_col = "time_ns" if "time_ns" in peaks_df.columns else ("x" if "x" in peaks_df.columns else None)
        if t_col is None:
            return None

        if pick == "earliest":
            return float(peaks_df[t_col].min())
        if pick == "latest":
            return float(peaks_df[t_col].max())
        if pick == "max_amplitude":
            a_col = "amplitude" if "amplitude" in peaks_df.columns else ("y" if "y" in peaks_df.columns else None)
            if a_col is None:
                return float(peaks_df[t_col].min())
            idx = peaks_df[a_col].astype(float).idxmax()
            return float(peaks_df.loc[idx, t_col])

        return float(peaks_df[t_col].min())
    except Exception:
        return None
