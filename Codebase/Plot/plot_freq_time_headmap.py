from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt


def _infer_span_mhz(metadata) -> float:
    """
    Pick a reasonable +/- span (MHz) that includes baseband, sync, and TX tones,
    with a small margin, and never exceeds Nyquist.
    """
    base = float(metadata.baseband_hz)
    nyquist_hz = float(metadata.sample_rate_hz) / 2.0

    # Include offsets to known tones (if present)
    offsets = [0.0]
    for attr in ("sync_hz", "signal_tx_hz"):
        if hasattr(metadata, attr):
            offsets.append(float(getattr(metadata, attr)) - base)

    max_off_hz = max(abs(o) for o in offsets)

    margin_hz = 0.5e6  # 0.5 MHz visual margin
    span_hz = min(max_off_hz + margin_hz, nyquist_hz)

    # Ensure non-zero span for plotting
    if span_hz <= 0:
        span_hz = min(1.0e6, nyquist_hz)

    return span_hz / 1e6


def plot_freq_time_heatmap(
    metadata,
    iq: np.ndarray,
    *,
    span_mhz: float | None = None,
    window_size: int = 4096,
    overlap: float = 100,
    show: bool = True,
    save_path: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
):
    """
    Plot a time-frequency heatmap from IQ data.

    X-axis: time (nanoseconds)
    Y-axis: frequency offset from center (MHz), centered at 0
    Color: amplitude (dB)

    Required
    --------
    metadata : object
        Must provide:
            - metadata.sample_rate_hz
            - metadata.baseband_hz
        Optionally:
            - metadata.sync_hz
            - metadata.signal_tx_hz
    iq : np.ndarray
        Complex IQ samples (np.complex64/128), or array convertible to complex.

    Optional
    --------
    span_mhz : float | None
        +/- frequency span to display (in MHz). If None, inferred from metadata
        (sync/tx offsets) and capped at Nyquist.
    """
    # Pull from metadata
    sample_rate_hz = float(metadata.sample_rate_hz)
    center_freq_hz = float(metadata.baseband_hz)

    # Span selection
    if span_mhz is None:
        span_mhz = _infer_span_mhz(metadata)

    # Ensure IQ is a numpy array
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

    span_hz = float(span_mhz) * 1e6
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

        segment_win = segment * window

        spectrum = np.fft.fft(segment_win)
        spectrum = np.fft.fftshift(spectrum)
        mag = np.abs(spectrum)

        frames[i, :] = mag[mask]

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
    if len(times_ns) > 1:
        dt_ns = float(np.median(np.diff(times_ns)))
    else:
        dt_ns = window_size / sample_rate_hz * 1e9

    if len(freqs_sel_mhz) > 1:
        df_mhz = float(np.median(np.diff(freqs_sel_mhz)))
    else:
        df_mhz = float(span_mhz) * 2.0

    time_edges_ns = np.concatenate(([times_ns[0] - dt_ns / 2.0], times_ns + dt_ns / 2.0))
    time_edges_ns[0] = max(time_edges_ns[0], 0.0)

    freq_edges_mhz = np.concatenate(([freqs_sel_mhz[0] - df_mhz / 2.0], freqs_sel_mhz + df_mhz / 2.0))

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(10, 6))

    img = ax.pcolormesh(
        time_edges_ns,
        freq_edges_mhz,
        mag_db.T,
        shading="auto",
        vmin=vmin,
        vmax=vmax,
    )

    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Frequency offset from center (MHz)")
    ax.set_title(
        f"Frequency–Time Amplitude\n"
        f"Center: {center_freq_hz/1e6:.3f} MHz, Span: ±{float(span_mhz):.3f} MHz"
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
