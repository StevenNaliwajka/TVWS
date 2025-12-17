import numpy as np

def apply_fft_mask(iq: np.ndarray, sample_rate_hz: float, keep_mask: np.ndarray) -> np.ndarray:
    """
    Hard frequency-domain masking: FFT -> zero bins -> IFFT.
    """
    if iq.ndim != 1:
        raise ValueError("iq must be a 1D complex numpy array")

    n = iq.size
    if n == 0:
        return iq

    spectrum = np.fft.fft(iq)
    spectrum[~keep_mask] = 0
    return np.fft.ifft(spectrum).astype(np.complex64, copy=False)