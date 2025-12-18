# Codebase/Analysis/plot_amplitude_freq.py

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt


def _infer_span_mhz(metadata) -> float:
    """
    Pick a reasonable +/- span (MHz) that includes baseband, sync, and TX tones,
    with a small margin, and never exceeds Nyquist.
    """
    base = float(getattr(metadata, "baseband_hz", 0.0))
    nyquist_hz = float(metadata.sample_rate_hz) / 2.0

    offsets = [0.0]
    for attr in ("sync_hz", "signal_tx_hz"):
        if hasattr(metadata, attr):
            offsets.append(float(getattr(metadata, attr)) - base)

    max_off_hz = max(abs(o) for o in offsets)
    margin_hz = 0.5e6
    span_hz = min(max_off_hz + margin_hz, nyquist_hz)

    if span_hz <= 0:
        span_hz = min(1.0e6, nyquist_hz)

    return span_hz / 1e6


def plot_amplitude_freq(
    metadata,
    iq: np.ndarray,
    *,
    span_mhz: float | None = None,
    window_size: int = 4096,
    overlap: float = 0.5,
    average: str = "median",
    detrend: bool = False,
    show: bool = True,
    save_path: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
):
    """
    Plot amplitude vs frequency over the *entire* IQ capture by averaging spectra
    across time windows.

    X-axis: frequency offset from center (MHz), centered at 0
    Y-axis: amplitude (dB)

    Required
    --------
    metadata : object
        Must provide:
            - metadata.sample_rate_hz
            - metadata.baseband_hz (optional, used for title and span inference)
        Optionally:
            - metadata.sync_hz
            - metadata.signal_tx_hz
    iq : np.ndarray
        Complex IQ samples.

    Optional
    --------
    span_mhz : float | None
        +/- frequency span to display (in MHz). If None, inferred from metadata
        (sync/tx offsets) and capped at Nyquist.
    window_size : int
        FFT size per frame.
    overlap : float
        If < 1.0, interpreted as fractional overlap in [0.0, 1.0).
        If >= 1.0, interpreted as hop size in samples.
    average : str
        How to average across frames:
            - "mean"   : mean(magnitude)
            - "median" : median(magnitude) (default, robust to bursts)
            - "max"    : max(magnitude)
            - "power"  : mean power then sqrt (RMS magnitude)
    detrend : bool
        If True, subtract complex mean per frame before FFT.
    vmin/vmax : float | None
        Optional Y-axis limits in dB.

    Returns
    -------
    freqs_sel_mhz : np.ndarray
        Frequency offsets (MHz) relative to center (0 = baseband_hz).
    mag_db : np.ndarray
        Averaged magnitude spectrum in dB.
    """
    sample_rate_hz = float(metadata.sample_rate_hz)
    center_freq_hz = float(getattr(metadata, "baseband_hz", 0.0))

    if span_mhz is None:
        span_mhz = _infer_span_mhz(metadata)

    iq = np.asarray(iq, dtype=np.complex64)

    if iq.size < window_size:
        raise ValueError("IQ data shorter than window size.")

    # --- Determine hop_size dynamically from overlap parameter ---
    if overlap < 1.0:
        if overlap < 0.0 or overlap >= 1.0:
            raise ValueError("Fractional overlap must be in [0.0, 1.0).")
        hop_size = int(window_size * (1.0 - overlap))
        if hop_size <= 0:
            hop_size = 1
    else:
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

    # --- Frequency axis ---
    freqs_hz = np.fft.fftfreq(window_size, d=1.0 / sample_rate_hz)
    freqs_hz = np.fft.fftshift(freqs_hz)

    span_hz = float(span_mhz) * 1e6
    mask = np.abs(freqs_hz) <= span_hz
    freqs_sel_hz = freqs_hz[mask]
    freqs_sel_mhz = freqs_sel_hz / 1e6

    window = np.hanning(window_size).astype(np.float32)

    # Accumulators for different averaging strategies
    average = average.strip().lower()
    if average not in {"mean", "median", "max", "power"}:
        raise ValueError('average must be one of: "mean", "median", "max", "power".')

    if average == "median":
        # Store per-frame mags for robust median (more memory, but simple/clear)
        mags = np.empty((n_frames, freqs_sel_hz.size), dtype=np.float32)
    elif average == "max":
        mag_acc = np.full(freqs_sel_hz.size, -np.inf, dtype=np.float32)
    elif average == "power":
        pow_acc = np.zeros(freqs_sel_hz.size, dtype=np.float64)
    else:  # mean
        mag_acc = np.zeros(freqs_sel_hz.size, dtype=np.float64)

    for i in range(n_frames):
        start = i * hop_size
        segment = iq[start : start + window_size]

        if detrend:
            segment = segment - np.mean(segment)

        segment_win = segment * window

        spectrum = np.fft.fft(segment_win)
        spectrum = np.fft.fftshift(spectrum)
        mag = np.abs(spectrum).astype(np.float32)

        mag_sel = mag[mask]

        if average == "median":
            mags[i, :] = mag_sel
        elif average == "max":
            mag_acc = np.maximum(mag_acc, mag_sel)
        elif average == "power":
            pow_acc += (mag_sel.astype(np.float64) ** 2)
        else:  # mean
            mag_acc += mag_sel.astype(np.float64)

    if average == "median":
        mag_out = np.median(mags, axis=0).astype(np.float32)
    elif average == "max":
        mag_out = mag_acc.astype(np.float32)
    elif average == "power":
        mag_out = np.sqrt(pow_acc / float(n_frames)).astype(np.float32)
    else:  # mean
        mag_out = (mag_acc / float(n_frames)).astype(np.float32)

    # --- Convert to dB ---
    eps = 1e-12
    mag_db = 20.0 * np.log10(mag_out + eps)

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(freqs_sel_mhz, mag_db)

    ax.set_xlabel("Frequency offset from center (MHz)")
    ax.set_ylabel("Amplitude (dB)")
    title_center = f"{center_freq_hz/1e6:.3f} MHz" if center_freq_hz else "N/A"
    ax.set_title(
        f"Amplitude–Frequency (avg={average})\n"
        f"Center: {title_center}, Span: ±{float(span_mhz):.3f} MHz, "
        f"Fs: {sample_rate_hz/1e6:.3f} MHz, FFT: {window_size}, Hop: {hop_size}"
    )
    ax.grid(True, alpha=0.3)

    if vmin is not None or vmax is not None:
        ax.set_ylim(vmin, vmax)

    plt.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=300)

    if show:
        plt.show()
    else:
        plt.close(fig)

    return freqs_sel_mhz, mag_db
