from __future__ import annotations

from typing import Optional

from findpeaks import findpeaks
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def detect_peaks_in_iq(
    meta_data,
    iq,
    method: str = "peakdetect",
    min_height: Optional[float] = None,
) -> pd.DataFrame:
    """
    Detect peaks in an IQ array and return their times in nanoseconds.

    meta_data is an object with attributes like:
      - meta_data.sample_rate_hz
      - meta_data.qty_peaks   (number of highest peaks to keep)
    """

    # Pull sample rate from metadata
    if not hasattr(meta_data, "sample_rate_hz"):
        raise AttributeError("meta_data must have attribute: sample_rate_hz")

    sample_rate_hz = float(meta_data.sample_rate_hz)
    if sample_rate_hz <= 0:
        raise ValueError(f"meta_data.sample_rate_hz must be > 0. Got: {sample_rate_hz}")

    # Pull qty_peaks from metadata
    if not hasattr(meta_data, "qty_peaks"):
        raise AttributeError("meta_data must have attribute: qty_peaks")

    qty_peaks = int(meta_data.qty_peaks)
    if qty_peaks < 0:
        raise ValueError(f"meta_data.qty_peaks must be >= 0. Got: {qty_peaks}")

    # 2) Magnitude vs time
    mag = np.abs(iq)

    # 3) Time axis in nanoseconds
    dt_ns = 1e9 / sample_rate_hz  # ns per sample
    t_ns = np.arange(mag.size, dtype=np.float64) * dt_ns

    # 4) Run findpeaks
    fp = findpeaks(method=method, whitelist=["peak"])
    results = fp.fit(mag, x=t_ns)  # x = time in ns

    df = results["df"]

    # Keep only the detected peaks
    peaks_df = df[df["peak"] == True].copy()

    # Optional: filter by minimum amplitude
    if min_height is not None:
        peaks_df = peaks_df[peaks_df["y"] >= float(min_height)]

    # Keep ONLY the N highest peaks by amplitude (y)
    # (Applied AFTER min_height so you get the highest among the allowed peaks.)
    if qty_peaks == 0:
        peaks_df = peaks_df.iloc[0:0].copy()
    elif len(peaks_df) > qty_peaks:
        peaks_df = peaks_df.nlargest(qty_peaks, "y").copy()

    # Sort by time BEFORE renaming, to be explicit we're sorting on x
    peaks_df = peaks_df.sort_values("x").reset_index(drop=True)

    # Rename for clarity
    peaks_df = peaks_df.rename(columns={"x": "time_ns", "y": "amplitude"})

    # ---- Print peaks sorted by time ----
    #print("\n[detect_peaks_in_iq] Detected peaks (top-N by amplitude, sorted by time):")
    #for _, row in peaks_df.iterrows():
    #    print(f"  t = {row['time_ns']:.3f} ns, amplitude = {row['amplitude']:.6f}")

    # ---- Plot magnitude with peaks marked ----
    fig, ax = plt.subplots()
    ax.plot(t_ns, mag, label="|IQ| (magnitude)")
    if not peaks_df.empty:
        ax.scatter(
            peaks_df["time_ns"],
            peaks_df["amplitude"],
            marker="x",
            s=40,
            label=f"Top {min(qty_peaks, len(peaks_df))} peaks",
        )

    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Amplitude (|IQ|)")
    ax.set_title("HackRF IQ Magnitude with Detected Peaks")
    ax.legend()
    ax.grid(True)

    plt.tight_layout()
    # plt.show()

    return peaks_df
