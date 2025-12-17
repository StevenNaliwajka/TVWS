# Codebase/Signal/Filter/frequency_filters.py

from __future__ import annotations

import numpy as np

from Codebase.Calculations.compute_tx_offset import compute_tx_offset
from Codebase.Filter.Scripts.apply_fft_mask import apply_fft_mask


def bandpass_filter(meta_data, iq):
    """
    Returns a function that filters OUT:
      - baseband (0 Hz offset), and
      - everything BETWEEN signal_tx_hz and sync_hz (inclusive)

    Practically: it NOTCHES the entire band [min_off, max_off] around DC,
    leaving only the two "outer" side regions (< min_off) and (> max_off).

    Usage:
        f = filter_middle_freq(MetaDataObj)
        iq2 = f(iq)
    """
    fs = float(meta_data.sample_rate_hz)

    min_off, max_off = compute_tx_offset(meta_data)

    n = iq.size
    freqs = np.fft.fftfreq(n, d=1.0 / fs)  # Hz, relative to baseband (0 Hz)
    # keep ONLY outside the middle band (this removes DC automatically)
    keep = (freqs < min_off) | (freqs > max_off)
    final = apply_fft_mask(iq, fs, keep)
    return final