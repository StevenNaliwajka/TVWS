from findpeaks import findpeaks
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from Codebase.load_hackrf_iq import load_hackrf_iq


def detect_peaks_in_iq(
    iq_path: str,
    sample_rate_hz: float,
    method: str = "peakdetect",
    min_height: float | None = None,
) -> pd.DataFrame:
    """
    Detect peaks in a HackRF .iq file and return their times in nanoseconds.

    Parameters
    ----------
    iq_path : str
        Path to the .iq file.
    sample_rate_hz : float
        Sample rate used when recording (e.g. 10e6 for 10 Msps).
    method : str
        findpeaks method: 'peakdetect', 'topology', or 'caerus'.
    min_height : float, optional
        Minimum amplitude (on |IQ|) for a point to be kept as a peak.

    Returns
    -------
    peaks_df : pandas.DataFrame
        Columns:
            - time_ns: time of the peak in nanoseconds
            - amplitude: |IQ| at the peak
            - peak: True for peaks (all rows here)
            - (plus any extra columns from findpeaks, e.g. score, rank)
    """
    # 1) Load complex IQ
    iq = load_hackrf_iq(iq_path)

    # 2) Magnitude vs time
    mag = np.abs(iq)

    # 3) Time axis in nanoseconds
    dt_ns = 1e9 / float(sample_rate_hz)  # ns per sample
    t_ns = np.arange(mag.size, dtype=np.float64) * dt_ns

    # 4) Run findpeaks
    fp = findpeaks(method=method, whitelist=['peak'])
    results = fp.fit(mag, x=t_ns)   # x = time in ns

    df = results["df"]

    # Keep only the detected peaks
    peaks_df = df[df["peak"] == True].copy()

    # Optional: filter by minimum amplitude
    if min_height is not None:
        peaks_df = peaks_df[peaks_df["y"] >= min_height]

    # Sort by time BEFORE renaming, to be explicit we're sorting on x
    peaks_df = peaks_df.sort_values("x").reset_index(drop=True)

    # Rename for clarity
    peaks_df = peaks_df.rename(columns={"x": "time_ns", "y": "amplitude"})

    # ---- Print peaks sorted by time ----
    print("\n[detect_peaks_in_iq] Detected peaks (sorted by time):")
    for _, row in peaks_df.iterrows():
        print(f"  t = {row['time_ns']:.3f} ns, amplitude = {row['amplitude']:.6f}")

    # ---- Plot magnitude with peaks marked ----
    fig, ax = plt.subplots()
    ax.plot(t_ns, mag, label="|IQ| (magnitude)")
    if not peaks_df.empty:
        ax.scatter(
            peaks_df["time_ns"],
            peaks_df["amplitude"],
            marker="x",
            s=40,
            label="Detected peaks",
        )

    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Amplitude (|IQ|)")
    ax.set_title("HackRF IQ Magnitude with Detected Peaks")
    ax.legend()
    ax.grid(True)

    plt.tight_layout()
    plt.show()

    return peaks_df
