from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from Codebase.ProcessSignal.load_hackrf_iq import load_hackrf_iq


def plot_freq_time_heatmap(
    iq_path: str,
    sample_rate_hz: float,
    center_freq_hz: float,
    span_mhz: float,
    window_size: int = 4096,
    overlap: float = 100,
    show: bool = True,
    save_path: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
):
    """
    Plot a time-frequency heatmap from a HackRF .iq file.

    X-axis: time (nanoseconds)
    Y-axis: frequency offset from center (MHz), centered at 0
    Color: amplitude (dB)

    Parameters
    ----------
    iq_path : str
        Path to the HackRF .iq file.
    sample_rate_hz : float
        Sample rate used when recording (e.g. 10e6 for 10 Msps).
    center_freq_hz : float
        RF center frequency in Hz (used for labeling only).
    span_mhz : float
        +/- frequency span to display (in MHz). Example: 5 -> show -5 to +5 MHz.
    window_size : int
        FFT window size (number of samples per time slice).
    overlap : float
        If < 1.0, treated as fractional overlap between windows (0.0 to <1.0).
        If >= 1.0, treated as hop size in samples (i.e., distance between
        successive windows). With a fixed hop size and larger window_size,
        the effective fractional overlap grows automatically.
    show : bool
        If True, call plt.show() at the end.
    save_path : str or None
        If not None, save the figure to this path.
    vmin, vmax : float or None
        Optional fixed color scale limits in dB. If None, they are chosen
        from data percentiles for better contrast.

    Returns
    -------
    times_ns : np.ndarray
        1D array of time values (nanoseconds), length = number of time slices.
    freqs_sel_mhz : np.ndarray
        1D array of frequency offsets (MHz).
    mag_db : np.ndarray
        2D array of amplitudes in dB, shape = (len(times_ns), len(freqs_sel_mhz)).
        (Rows = time slices, columns = frequencies.)
    """
    # Load IQ data
    iq = load_hackrf_iq(iq_path)
    iq = np.asarray(iq)

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
        # Ensure at least 1-sample hop and at most window_size-1
        if hop_size >= window_size:
            hop_size = window_size - 1

    # Number of frames we can get with this hop_size
    n_frames = 1 + (iq.size - window_size) // hop_size
    if n_frames <= 0:
        raise ValueError(
            "Not enough samples for given window_size and hop/overlap settings."
        )

    # --- Frequency axis ---
    freqs_hz = np.fft.fftfreq(window_size, d=1.0 / sample_rate_hz)
    freqs_hz = np.fft.fftshift(freqs_hz)  # center 0 Hz

    span_hz = span_mhz * 1e6
    mask = np.abs(freqs_hz) <= span_hz
    freqs_sel_hz = freqs_hz[mask]
    freqs_sel_mhz = freqs_sel_hz / 1e6  # offset from center in MHz

    # --- Time-frequency matrix ---
    window = np.hanning(window_size).astype(np.float32)

    frames = np.empty((n_frames, freqs_sel_hz.size), dtype=np.float32)
    times_sec = np.empty(n_frames, dtype=np.float64)

    for i in range(n_frames):
        start = i * hop_size
        segment = iq[start : start + window_size]

        # Apply window
        segment_win = segment * window

        # FFT, shift, magnitude
        spectrum = np.fft.fft(segment_win)
        spectrum = np.fft.fftshift(spectrum)
        mag = np.abs(spectrum)

        # Keep only desired frequency range
        frames[i, :] = mag[mask]

        # Time at center of the window (in seconds)
        center_idx = start + window_size / 2.0
        times_sec[i] = center_idx / float(sample_rate_hz)

    times_ns = times_sec * 1e9  # convert to nanoseconds

    # --- Convert amplitude to dB ---
    eps = 1e-12
    mag_db = 20.0 * np.log10(frames + eps)

    # Choose color scale for more detail if not specified
    if vmin is None:
        vmin = np.percentile(mag_db, 5)
    if vmax is None:
        vmax = np.percentile(mag_db, 99)

    # --- Build bin edges so axes line up correctly with pcolormesh ---
    # Assume approximately uniform spacing
    if len(times_ns) > 1:
        dt_ns = float(np.median(np.diff(times_ns)))
    else:
        dt_ns = window_size / sample_rate_hz * 1e9

    if len(freqs_sel_mhz) > 1:
        df_mhz = float(np.median(np.diff(freqs_sel_mhz)))
    else:
        df_mhz = span_mhz * 2.0

    time_edges_ns = np.concatenate(
        ([times_ns[0] - dt_ns / 2.0], times_ns + dt_ns / 2.0)
    )
    # Clamp to start at 0
    time_edges_ns[0] = max(time_edges_ns[0], 0.0)

    freq_edges_mhz = np.concatenate(
        ([freqs_sel_mhz[0] - df_mhz / 2.0], freqs_sel_mhz + df_mhz / 2.0)
    )

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(10, 6))

    img = ax.pcolormesh(
        time_edges_ns,        # X edges: time (ns)
        freq_edges_mhz,       # Y edges: frequency offset (MHz)
        mag_db.T,             # Color: amplitude (dB), shape (freq, time)
        shading="auto",
        vmin=vmin,
        vmax=vmax,
    )

    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Frequency offset from center (MHz)")
    ax.set_title(
        f"Frequency–Time Amplitude\n"
        f"Center: {center_freq_hz/1e6:.3f} MHz, Span: ±{span_mhz:.3f} MHz"
    )

    cbar = fig.colorbar(img, ax=ax)
    cbar.set_label("Amplitude (dB)")

    plt.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=300)

    if show:
        plt.show()
    else:
        plt.close(fig)

    return times_ns, freqs_sel_mhz, mag_db
