import numpy as np

from Codebase.Calculations.compute_tx_offset import compute_tx_offset
from Codebase.Filter.Scripts.apply_fft_mask import apply_fft_mask


def upper_filter(meta_data, iq):
    """
    Filters OUT everything ABOVE a scaled upper edge.
    Uses meta_data.edge_percentage to move the cutoff slightly inward toward DC,
    leaving a little “outer leftover” just like your bandpass (notch) logic.

    Example (if max_off ~ +2 MHz):
        edge_percentage=0.95 -> cutoff becomes +1.9 MHz (less constricting)
        so we keep freqs <= +1.9 MHz.
    """
    fs = float(meta_data.sample_rate_hz)

    min_off, max_off = compute_tx_offset(meta_data)

    edge_percentage = float(meta_data.edge_percentage)
    if not (0.0 < edge_percentage < 1.0):
        raise ValueError(
            f"meta_data.edge_percentage must be between 0 and 1 (exclusive). Got: {edge_percentage}"
        )

    # Scale the upper edge toward 0 Hz (max_off is typically positive)
    max_cut = float(max_off) * edge_percentage

    n = iq.size
    freqs = np.fft.fftfreq(n, d=1.0 / fs)  # Hz, relative to baseband (0 Hz)

    keep = freqs <= max_cut
    return apply_fft_mask(iq, fs, keep)
