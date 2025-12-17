import numpy as np

from Codebase.Calculations.compute_tx_offset import compute_tx_offset
from Codebase.Filter.Scripts.apply_fft_mask import apply_fft_mask


def upper_filter(meta_data, iq):
    """
    Filters OUT everything ABOVE a scaled upper edge.

    Uses meta_data.edge_percentage such that values < 1.0 expand the cutoff outward
    (more positive), e.g.:
        max_off ~ +2.0 MHz
        edge_percentage=0.95 -> max_cut = +2.0 / 0.95 ≈ +2.105 MHz (~ +2.1 MHz)

    So we keep freqs <= max_cut.
    """
    fs = float(meta_data.sample_rate_hz)

    min_off, max_off = compute_tx_offset(meta_data)

    edge_percentage = float(meta_data.edge_percentage)
    if not (0.0 < edge_percentage < 1.0):
        raise ValueError(
            f"meta_data.edge_percentage must be between 0 and 1 (exclusive). Got: {edge_percentage}"
        )

    # max_off is typically positive; dividing by <1 makes it MORE positive (e.g., +2 -> +2.1)
    max_cut = float(max_off) / edge_percentage

    n = iq.size
    freqs = np.fft.fftfreq(n, d=1.0 / fs)  # Hz, relative to baseband (0 Hz)

    keep = freqs <= max_cut
    return apply_fft_mask(iq, fs, keep)
