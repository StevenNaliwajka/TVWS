# Codebase/Signal/Filter/frequency_filters.py

from __future__ import annotations

import numpy as np

from Codebase.Processing.compute_tx_offset import compute_tx_offset
from Codebase.Filter.Scripts.apply_fft_mask import apply_fft_mask


def bandpass_filter(meta_data, iq):
    """
    NOTE: This is actually a BAND-STOP (notch) in frequency domain.

    Removes the middle band around DC:
        [-edge_hz, +edge_hz]
    where:
        edge_hz = meta_data.edge_percentage * ref_edge_hz

    ref_edge_hz is derived from metadata offsets (e.g., ~2 MHz).
    Example:
        edge_percentage = 0.95  -> keep the outer ~5% total (about ~2.5% on each side).
    """
    fs = float(meta_data.sample_rate_hz)

    min_off, max_off = compute_tx_offset(meta_data)  # typically ~(-2e6, +2e6)

    # Pull directly from metadata (required)
    edge_percentage = float(meta_data.edge_percentage)
    if not (0.0 < edge_percentage < 1.0):
        raise ValueError(
            f"meta_data.edge_percentage must be between 0 and 1 (exclusive). Got: {edge_percentage}"
        )

    # Reference edge: use the smaller magnitude of the two sides (safe if slightly asymmetric)
    ref_edge_hz = min(abs(float(min_off)), abs(float(max_off)))
    edge_hz = edge_percentage * ref_edge_hz

    min_cut, max_cut = -edge_hz, +edge_hz

    n = iq.size
    freqs = np.fft.fftfreq(n, d=1.0 / fs)  # Hz relative to baseband (0 Hz)

    # Remove the middle band + DC
    remove = (freqs >= min_cut) & (freqs <= max_cut)
    remove |= (freqs == 0.0)

    keep = ~remove
    final = apply_fft_mask(iq, fs, keep)
    return final
