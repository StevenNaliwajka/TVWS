import numpy as np

# ======================================================
# Fractional peak estimator (parabolic)
# ======================================================
def fractional_peak_detection(corr, alpha=0.2):
    corr_abs = np.abs(corr)

    # Find strongest peak
    k_max = np.argmax(corr_abs)
    A = corr_abs[k_max]

    # Constant-fraction threshold (alpha = 0.2–0.3 works well)
    T = A * alpha

    # Move left until sub-threshold
    i = k_max
    while i > 0 and corr_abs[i] > T:
        i -= 1

    # Safety: if no crossing found
    if i == 0:
        return float(i)

    # Linear interpolation for fractional-sample estimate
    y1 = corr_abs[i]
    y2 = corr_abs[i+1]

    # Avoid divide-by-zero
    if y2 == y1:
        return float(i)

    frac = (T - y1) / (y2 - y1)
    return i + frac
