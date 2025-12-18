import numpy as np
from Codebase.Processing.compute_tx_offset import compute_tx_offset
from Codebase.Filter.Scripts.apply_fft_mask import apply_fft_mask


def lower_filter(meta_data, iq):
    """
    Filters OUT everything BELOW a scaled lower edge.

    Uses meta_data.edge_percentage such that values < 1.0 expand the cutoff outward
    (more negative), e.g.:
        min_off ~ -2.0 MHz
        edge_percentage=0.95 -> min_cut = -2.0 / 0.95 ≈ -2.105 MHz (~ -2.1 MHz)

    So we keep freqs >= min_cut (slightly less constricting on the low side).
    """
    fs = float(meta_data.sample_rate_hz)

    min_off, max_off = compute_tx_offset(meta_data)

    edge_percentage = float(meta_data.edge_percentage)
    if not (0.0 < edge_percentage < 1.0):
        raise ValueError(
            f"meta_data.edge_percentage must be between 0 and 1 (exclusive). Got: {edge_percentage}"
        )

    # min_off is typically negative; dividing by <1 makes it MORE negative (e.g., -2 -> -2.1)
    min_cut = float(min_off) / edge_percentage

    n = iq.size
    freqs = np.fft.fftfreq(n, d=1.0 / fs)  # Hz, relative to baseband (0 Hz)

    keep = freqs >= min_cut
    result = apply_fft_mask(iq, fs, keep)
    return result
