import numpy as np
from Codebase.Calculations.compute_tx_offset import compute_tx_offset
from Codebase.Filter.Scripts.apply_fft_mask import apply_fft_mask


def lower_filter(meta_data, iq):
    """
    Filters OUT everything BELOW a scaled lower edge.
    Uses meta_data.edge_percentage to move the cutoff slightly inward toward DC,
    leaving a little “outer leftover” just like your bandpass (notch) logic.

    Example (if min_off ~ -2 MHz):
        edge_percentage=0.95 -> cutoff becomes -1.9 MHz (less constricting)
        so we keep freqs >= -1.9 MHz.
    """
    fs = float(meta_data.sample_rate_hz)

    min_off, max_off = compute_tx_offset(meta_data)

    edge_percentage = float(meta_data.edge_percentage)
    if not (0.0 < edge_percentage < 1.0):
        raise ValueError(
            f"meta_data.edge_percentage must be between 0 and 1 (exclusive). Got: {edge_percentage}"
        )

    # Scale the lower edge toward 0 Hz (min_off is typically negative)
    min_cut = float(min_off) * edge_percentage

    n = iq.size
    freqs = np.fft.fftfreq(n, d=1.0 / fs)  # Hz, relative to baseband (0 Hz)

    keep = freqs >= min_cut
    result = apply_fft_mask(iq, fs, keep)
    return result
