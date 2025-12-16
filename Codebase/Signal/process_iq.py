# process_iq.py

import numpy as np
from scipy.signal import butter, sosfiltfilt

# Default assumptions for your HackRF setup
DEFAULT_FS = 20e6        # 20 MHz sample rate
DEFAULT_CUTOFF_HZ = 500e3  # 500 kHz low-pass cutoff (around DC)


def _design_butter_lowpass_sos(
    cutoff_hz: float,
    fs: float,
    order: int = 4
):
    """
    Design a low-pass Butterworth filter and return SOS coefficients.
    """
    nyq = 0.5 * fs
    norm_cutoff = cutoff_hz / nyq
    if not 0 < norm_cutoff < 1:
        raise ValueError(
            f"cutoff_hz must be between 0 and Nyquist (fs/2). "
            f"Got cutoff_hz={cutoff_hz}, fs={fs}, norm={norm_cutoff}"
        )

    sos = butter(order, norm_cutoff, btype="low", output="sos")
    return sos


def process_iq(
    iq: np.ndarray,
    fs: float = DEFAULT_FS,
    cutoff_hz: float = DEFAULT_CUTOFF_HZ,
    order: int = 4
) -> np.ndarray:
    """
    Apply a 4th-order Butterworth low-pass filter to complex IQ data to
    reduce noise and keep the carrier region near 0 Hz.

    Parameters
    ----------
    iq : np.ndarray
        Complex baseband IQ samples (1D array, dtype complex).
    fs : float, optional
        Sample rate in Hz. Default assumes 20 MHz HackRF capture.
    cutoff_hz : float, optional
        Low-pass cutoff frequency in Hz. Default = 500 kHz, which keeps
        the carrier at DC and nearby content while removing higher-frequency
        noise.
    order : int, optional
        Filter order. Default = 4 as requested.

    Returns
    -------
    np.ndarray
        Filtered complex IQ (same shape as input, dtype complex64).
    """
    iq = np.asarray(iq)

    if iq.ndim != 1:
        raise ValueError("process_iq expects a 1D complex IQ array.")

    # If the array is too short, filtering can get weird. In that case, just return as-is.
    if iq.size < 16:
        return iq.astype(np.complex64)

    # Design low-pass filter
    sos = _design_butter_lowpass_sos(
        cutoff_hz=cutoff_hz,
        fs=fs,
        order=order
    )

    # Zero-phase filtering to avoid phase distortion of the carrier
    filtered = sosfiltfilt(sos, iq)

    # Ensure a compact dtype for downstream processing
    return filtered.astype(np.complex64)


if __name__ == "__main__":
    # Simple sanity test / example (won't run during import)
    # This just shows usage; plug in your real .iq path + loader.
    from Codebase.ProcessSignal.load_hackrf_iq import load_hackrf_iq

    example_path = "example.iq"
    raw_iq = load_hackrf_iq(example_path)
    filtered_iq = process_iq(raw_iq)

    print("Loaded IQ shape:", raw_iq.shape)
    print("Filtered IQ shape:", filtered_iq.shape)
