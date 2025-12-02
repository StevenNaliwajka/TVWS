# Codebase/plot_freq_time_heatmap.py

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from Codebase.load_hackrf_iq import load_hackrf_iq


def plot_freq_time_heatmap(
    iq_path: str,
    sample_rate_hz: float,
    center_freq_hz: float,
    span_mhz: float,
    window_size: int = 4096,
    overlap: float = 0.5,
    show: bool = True,
    save_path: str | None = None,
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
        Fractional overlap between windows (0.0 to <1.0).
    show : bool
        If True, call plt.show() at the end.
    save_path : str or None
        If not None, save the figure to this path.

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

    hop_size = int(window_size * (1.0 - overlap))
    if hop_size <= 0:
        raise ValueError("overlap too large, hop_size becomes <= 0")

    # Frequency axis for one FFT
    freqs_hz = np.fft.fftfreq(window_size, d=1.0 / sample_rate_hz)
    freqs_hz = np.fft.fftshift(freqs_hz)  # center 0 Hz

    # Limit to desired +/- span
    span_hz = span_mhz * 1e6
    mask = np.abs(freqs_hz) <= span_hz
    freqs_sel_hz = freqs_hz[mask]
    freqs_sel_mhz = freqs_sel_hz / 1e6  # offset from center in MHz

    # Time-frequency matrix
    window = np.hanning(window_size)
    frames = []
    times_sec = []

    for start in range(0, iq.size - window_size + 1, hop_size):
        segment = iq[start : start + window_size]

        # Apply window
        segment_win = segment * window

        # FFT, shift, magnitude
        spectrum = np.fft.fft(segment_win)
        spectrum = np.fft.fftshift(spectrum)
        mag = np.abs(spectrum)

        # Keep only desired frequency range
        frames.append(mag[mask])

        # Time at center of the window (in seconds)
        center_idx = start + window_size // 2
        t_sec = center_idx / float(sample_rate_hz)
        times_sec.append(t_sec)

    frames = np.array(frames)        # shape: (n_times, n_freqs)
    times_sec = np.array(times_sec)  # seconds
    times_ns = times_sec * 1e9       # convert to nanoseconds

    # Convert amplitude to dB
    eps = 1e-12
    mag_db = 20.0 * np.log10(frames + eps)

    # Plot: X = time (ns), Y = frequency → need mag_db.T (freq x time)
    fig, ax = plt.subplots(figsize=(10, 6))
    img = ax.pcolormesh(
        times_ns,        # X: time (ns)
        freqs_sel_mhz,   # Y: frequency offset (MHz)
        mag_db.T,        # Color: amplitude (dB)
        shading="auto",
    )

    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Frequency offset from center (MHz)")
    ax.set_title(
        f"Frequency–Time Amplitude\nCenter: {center_freq_hz/1e6:.3f} MHz, Span: ±{span_mhz:.3f} MHz"
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
