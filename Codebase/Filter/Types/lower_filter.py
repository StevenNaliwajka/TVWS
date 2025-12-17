import numpy as np
from Codebase.Calculations.compute_tx_offset import compute_tx_offset
from Codebase.Filter.Scripts.apply_fft_mask import apply_fft_mask


def lower_filter(meta_data, iq):
    """
    Returns a function that filters OUT everything BELOW the lowest of (sync_hz, signal_tx_hz).
    I.e., keeps frequencies >= lowest_freq.

    Usage:
        f = filter_lower_freq(MetaDataObj)
        iq2 = f(iq)
    """
    fs = float(meta_data.sample_rate_hz)

    min_off, max_off = compute_tx_offset(meta_data)

    n = iq.size
    freqs = np.fft.fftfreq(n, d=1.0 / fs)  # Hz, relative to baseband (0 Hz)
    keep = freqs >= min_off
    result = apply_fft_mask(iq, fs, keep)
    return result
