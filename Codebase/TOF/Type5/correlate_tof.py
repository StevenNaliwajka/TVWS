import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate
from scipy.signal import firwin, lfilter

from Codebase.PeakDetection.Type2.fractional_peak_detection import fractional_peak_detection


def correlate_tof():
    # ======================================================
    # CORRELATION
    # mode='full' so the peak position reveals offset
    # ======================================================
    print("Computing correlation...")
    corr = correlate(rx, pilot.conj(), mode='full')
    corr_norm = correlate(pilot, pilot.conj(), mode='full')
    corr_norm = np.abs(corr_norm)
    k = np.argmax(corr_norm)
    A = corr_norm[k]

    # Find peak
    peak = fractional_peak_detection(corr)
    Npilot = len(pilot)

    # Sample delay = peak_index - (Npilot - 1)
    delay_samples = peak - (Npilot - 1)

    # fs = 20 MHz if that's your sample rate
    fs = 20_000_000
    delay_ns = (peak / fs) * 1e9