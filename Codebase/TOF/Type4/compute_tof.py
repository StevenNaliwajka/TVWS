# Codebase/Processing/compute_tof.py
from __future__ import annotations

from typing import Any, Optional

from Codebase.PeakDetection.Type1.detect_peaks_in_iq import detect_peaks_in_iq


def compute_tof(meta_data: Any, signal: Any) -> Optional[float]:
    """
    Ensure signal.tof is populated.

    Behavior:
      - If signal.tof already exists and is not None, return it unchanged.
      - Otherwise:
          1) detect_peaks_in_iq(meta_data, signal.iq)
          2) take the latest time (max time_ns among returned peaks)
          3) set signal.tof to that value (in ns)
          4) return signal.tof

    Returns:
      - tof in nanoseconds (float) if found
      - None if no peaks were returned
    """
    # If tof attribute doesn't exist yet, treat it as None
    existing = getattr(signal, "tof", None)
    if existing is not None:
        return float(existing)

    if not hasattr(signal, "iq"):
        raise AttributeError("signal must have attribute: iq")

    peaks_df = detect_peaks_in_iq(meta_data, signal.iq)

    # If no peaks, leave tof as None
    if peaks_df is None or getattr(peaks_df, "empty", True):
        setattr(signal, "tof", None)
        return None

    if "time_ns" not in peaks_df.columns:
        raise KeyError("detect_peaks_in_iq must return a DataFrame with a 'time_ns' column")

    # peaks_df is already sorted by time in your detect_peaks_in_iq, so last row is latest
    tof_ns = float(peaks_df["time_ns"].iloc[-1])

    setattr(signal, "tof", tof_ns)
    return tof_ns
