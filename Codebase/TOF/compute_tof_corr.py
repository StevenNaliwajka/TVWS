import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate
from scipy.signal import firwin, lfilter

from Codebase.PeakDetection.Type2.fractional_peak_detection import fractional_peak_detection


# ======================================================
# Load IQ file (HackRF int8 interleaved)
# ======================================================
def load_iq(filename):
    raw = np.fromfile(filename, dtype=np.int8)
    # Convert to complex64: interpret as I,Q,I,Q,...
    iq = raw.astype(np.float32).view(np.complex64)
    bandstop_taps = firwin(numtaps=301, cutoff=[0.3, 0.99], pass_zero=True)
    filtered_iq = lfilter(bandstop_taps, 1.0, iq)
    return filtered_iq


# ======================================================
# MAIN
# ======================================================
pilot_file = "pilot_last.iq"
rx_file = "20251119_18-23-32_1763594612_2_5in01616.iq"

print("Loading files...")
pilot = load_iq(pilot_file)
rx = load_iq(rx_file)

print(f"pilot samples: {len(pilot)}")
print(f"rx samples:    {len(rx)}")



print("\n==============================")
print("       CORRELATION RESULT")
print("==============================")
print(f"Peak Index        = {peak:.3f}")
#print(f"Delay (samples)   = {delay_samples:.3f}")
print(f"Peak (ns)        = {delay_ns:.3f} ns")
print("==============================\n")

# ======================================================
# PLOT THE CORRELATION
# ======================================================
plt.figure(figsize=(12,5))
plt.plot(np.abs(corr) / A, linewidth=1.0)
plt.title("Correlation Magnitude")
plt.xlabel("Sample Index")
plt.ylabel("|corr|")
plt.grid(True)

plt.axvline(peak, color='r', linestyle='--', label=f"Peak @ {peak:.1f}")
plt.legend()
plt.tight_layout()
plt.show()

