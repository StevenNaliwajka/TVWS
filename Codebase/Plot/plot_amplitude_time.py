# Codebase/Analysis/plot_amplitude_time.py

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt


def plot_amplitude_time(
    metadata,
    iq: np.ndarray,
    *,
    window_size: int = 4096,
    overlap: float = 100,
    mode: str = "rms",
    detrend: bool = False,
    show: bool = True,
    save_path: str | None = None,
    max_points: int | None = 200_000,
):
    """
    Plot amplitude vs time from IQ data (framed in windows).

    X-axis: time (nanoseconds)
    Y-axis: amplitude (dB)

    Required
    --------
    metadata : object
        Must provide:
            - metadata.sample_rate_hz
        Optionally (used for title only):
            - metadata.baseband_hz
    iq : np.ndarray
        Complex IQ samples (np.complex64/128), or array convertible to complex.

    Optional
    --------
    window_size : int
        Samples per frame.
    overlap : float
        If < 1.0, interpreted as fractional overlap in [0.0, 1.0).
        If >= 1.0, interpreted as hop size in samples.
    mode : str
        How to compute amplitude per frame:
            - "rms"  : sqrt(mean(|x|^2))   (default, robust)
            - "mean" : mean(|x|)
            - "peak" : max(|x|)
    detrend : bool
        If True, subtract the complex mean of each frame before measuring amplitude
        (can reduce DC bias).
    max_points : int | None
        If not None and frames exceed this, decimate for plotting performance.

    Returns
    -------
    times_ns : np.ndarray
        Frame center times in nanoseconds.
    amp_db : np.ndarray
        Amplitude per frame in dB (20*log10(amplitude)).
    """
    sample_rate_hz = float(metadata.sample_rate_hz)
    center_freq_hz = float(getattr(metadata, "baseband_hz", 0.0))

    iq = np.asarray(iq, dtype=np.complex64)

    if iq.size < window_size:
        raise ValueError("IQ data shorter than window size.")

    # --- Determine hop_size dynamically from overlap parameter ---
    if overlap < 1.0:
        # Interpret as fractional overlap
        if overlap < 0.0 or overlap >= 1.0:
            raise ValueError("Fractional overlap must be in [0.0, 1.0).")
        hop_size = int(window_size * (1.0 - overlap))
        if hop_size <= 0:
            hop_size = 1
    else:
        # Interpret as hop size in samples
        hop_size = int(overlap)
        if hop_size <= 0:
            hop_size = 1
        if hop_size >= window_size:
            hop_size = window_size - 1

    n_frames = 1 + (iq.size - window_size) // hop_size
    if n_frames <= 0:
        raise ValueError(
            "Not enough samples for given window_size and hop/overlap settings."
        )

    mode = mode.strip().lower()
    if mode not in {"rms", "mean", "peak"}:
        raise ValueError('mode must be one of: "rms", "mean", "peak".')

    window = np.hanning(window_size).astype(np.float32)

    amps = np.empty(n_frames, dtype=np.float32)
    times_sec = np.empty(n_frames, dtype=np.float64)

    for i in range(n_frames):
        start = i * hop_size
        segment = iq[start : start + window_size]

        if detrend:
            segment = segment - np.mean(segment)

        segment_win = segment * window
        mag = np.abs(segment_win)

        if mode == "rms":
            amp = np.sqrt(np.mean(mag * mag))
        elif mode == "mean":
            amp = np.mean(mag)
        else:  # "peak"
            amp = np.max(mag)

        amps[i] = amp

        center_idx = start + window_size / 2.0
        times_sec[i] = center_idx / sample_rate_hz

    times_ns = times_sec * 1e9

    # --- Convert amplitude to dB ---
    eps = 1e-12
    amp_db = 20.0 * np.log10(amps + eps)

    # Optional decimation for plotting performance
    plot_times_ns = times_ns
    plot_amp_db = amp_db
    if max_points is not None and plot_times_ns.size > max_points:
        stride = int(np.ceil(plot_times_ns.size / max_points))
        plot_times_ns = plot_times_ns[::stride]
        plot_amp_db = plot_amp_db[::stride]

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(plot_times_ns, plot_amp_db)

    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Amplitude (dB)")
    title_center = f"{center_freq_hz/1e6:.3f} MHz" if center_freq_hz else "N/A"
    ax.set_title(
        f"Amplitude–Time ({mode.upper()})\n"
        f"Center: {title_center}, Fs: {sample_rate_hz/1e6:.3f} MHz, "
        f"Window: {window_size}, Hop: {hop_size}"
    )
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=300)

    if show:
        plt.show()
    else:
        plt.close(fig)

    return times_ns, amp_db
