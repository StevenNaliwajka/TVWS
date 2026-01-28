import numpy as np
from scipy.signal import welch, correlate, butter, filtfilt

import tkinter as tk
from tkinter import filedialog
from pathlib import Path

from Codebase.Filter.filter_singal import filter_signal

from Codebase.Object.metadata_object import MetaDataObj

EPS = 1e-12
FS = 20e6


def compare_before_after(iq_path, pilot, wn, filtering, MetaDataObj, filter_signal):
    x_before, x_after = load_iq_with_optional_filter(
        iq_path=iq_path,
        wn=wn,
        filtering=filtering,
        MetaDataObj=MetaDataObj,
        filter_signal=filter_signal
    )

    m_before = wired_vs_pilot_metrics(x_before, pilot)
    m_after  = wired_vs_pilot_metrics(x_after,  pilot)

    print("=== BEFORE filtering ===")
    print(f"rho: {m_before['rho_corr_norm']:.4f}, EVM%: {m_before['evm_percent']:.2f}, offset: {m_before['pilot_offset']}")

    print("=== AFTER filtering ===")
    print(f"rho: {m_after['rho_corr_norm']:.4f}, EVM%: {m_after['evm_percent']:.2f}, offset: {m_after['pilot_offset']}")

    print("=== DELTA (after - before) ===")
    print(f"Δrho: {m_after['rho_corr_norm'] - m_before['rho_corr_norm']:+.4f}")
    print(f"ΔEVM%: {m_after['evm_percent'] - m_before['evm_percent']:+.2f}")

    return m_before, m_after
# ---------- IO ----------
def read_iq_int16(path: str) -> np.ndarray:
    """Read interleaved int16 IQ -> complex64."""
    x = np.fromfile(path, dtype=np.int16)
    i = x[0::2].astype(np.float32)
    q = x[1::2].astype(np.float32)
    return (i + 1j*q).astype(np.complex64)

def pick_directory(title="Select folder"):
    root = tk.Tk()
    root.withdraw()                 # hide main window
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title=title)
    root.destroy()
    return Path(folder) if folder else None

# ---------- Helpers ----------
def normalize_rms(x: np.ndarray) -> np.ndarray:
    rms = np.sqrt(np.mean(np.abs(x)**2)) + EPS
    return x / rms

def safe_prob(v: np.ndarray) -> np.ndarray:
    v = np.maximum(np.asarray(v, float), 0.0) + EPS
    return v / np.sum(v)

def kl_div(P: np.ndarray, Q: np.ndarray) -> float:
    P = safe_prob(P); Q = safe_prob(Q)
    return float(np.sum(P * np.log(P / Q)))

def js_div(P: np.ndarray, Q: np.ndarray) -> float:
    P = safe_prob(P); Q = safe_prob(Q)
    M = 0.5*(P + Q)
    return 0.5*kl_div(P, M) + 0.5*kl_div(Q, M)

def normalize_rms(x):
    return x / (np.sqrt(np.mean(np.abs(x)**2)) + EPS)

def psd_dist(x, fs, nperseg=8192):
    f, Pxx = welch(x, fs=fs, nperseg=nperseg, return_onesided=False, scaling="density")
    idx = np.argsort(f)
    return f[idx], safe_prob(Pxx[idx])

def band_select(f, P, f_low, f_high):
    m = (f >= f_low) & (f <= f_high)
    return f[m], safe_prob(P[m])

def wired_vs_ota_psd_div(wired: np.ndarray, ota: np.ndarray, pilot: np.ndarray,
                        fs=FS, nperseg=16384, f_low=None, f_high=None):
    kw = find_pilot_offset(wired, pilot)
    ko = find_pilot_offset(ota, pilot)

    # Compare equal-length windows starting at pilot
    L = min(len(wired) - kw, len(ota) - ko)
    w_win = normalize_rms(wired[kw:kw+L])
    o_win = normalize_rms(ota[ko:ko+L])

    fW, PW = psd_dist(w_win, fs, nperseg=nperseg)
    fO, PO = psd_dist(o_win, fs, nperseg=nperseg)

    if f_low is not None and f_high is not None:
        fW, PW = band_select(fW, PW, f_low, f_high)
        fO, PO = band_select(fO, PO, f_low, f_high)

    if len(PW) != len(PO) or not np.allclose(fW, fO):
        raise RuntimeError("Frequency grids differ — keep fs/nperseg/band limits identical.")

    return {
        "kw": kw, "ko": ko,
        "kl_psd": kl_div(PW, PO),
        "js_psd": js_div(PW, PO),
    }

def load_iq_int8(iq_path: str) -> np.ndarray:
    raw_data = np.fromfile(iq_path, dtype=np.int8)
    if raw_data.size < 4:
        raise ValueError("IQ file too small / empty.")

    I = raw_data[0::2].astype(np.float64)
    Q = raw_data[1::2].astype(np.float64)
    x = I + 1j * Q

    # DC offset removal
    x = x - np.mean(x)
    return x

def apply_bandpass_iq(x: np.ndarray, wn, order=4) -> np.ndarray:
    """
    wn should be normalized to Nyquist if you keep scipy butter default behavior:
      wn = [f1/(fs/2), f2/(fs/2)]
    """
    b, a = butter(N=order, Wn=wn, btype="bandpass")
    return filtfilt(b, a, x)

def load_iq_with_optional_filter(iq_path: str, wn, filtering: int, MetaDataObj, filter_signal):
    """
    Returns (iq_before, iq_after)
    - iq_before: DC-removed, (optionally) butter bandpass if filtering==1 (based on your code)
    - iq_after: output of filter_signal(metadata, iq_before) if filtering==1 else same as iq_before
    """
    iq_before = load_iq_int8(iq_path)

    metadata = MetaDataObj()

    iq_before = apply_bandpass_iq(iq_before, wn=wn, order=4)

    iq_after = filter_signal(metadata, iq_before)

    return iq_before, iq_after

def run_all(pilot_path, rx1_path, rx2_path, wn, filtering, MetaDataObj, filter_signal,
            f_low=-2e6, f_high=2e6):
    # Load pilot once (same pipeline: raw + filtered)
    pilot_before, pilot_after = load_iq_with_optional_filter(pilot_path, wn, filtering, MetaDataObj, filter_signal)

    # Load wired/ota
    rx1_before, rx1_after = load_iq_with_optional_filter(rx1_path, wn, filtering, MetaDataObj, filter_signal)
    rx2_before, rx2_after = load_iq_with_optional_filter(rx2_path, wn, filtering, MetaDataObj, filter_signal)

    # 1) pilot ↔ wired (rx1)
    p1_before = wired_vs_pilot_metrics(rx1_before, pilot_before)
    p1_after  = wired_vs_pilot_metrics(rx1_after,  pilot_after)

    # 2) wired (rx1) ↔ OTA (rx2)
    w2_before = wired_vs_ota_psd_div(rx1_before, rx2_before, pilot_before, fs=FS, f_low=f_low, f_high=f_high)
    w2_after  = wired_vs_ota_psd_div(rx1_after,  rx2_after,  pilot_after,  fs=FS, f_low=f_low, f_high=f_high)

    print("\n=== Pilot ↔ Wired (rx1) ===")
    print(f"BEFORE: rho={p1_before['rho_corr_norm']:.4f}, EVM={p1_before['evm_percent']:.2f}%, offset={p1_before['pilot_offset']}")
    print(f"AFTER : rho={p1_after['rho_corr_norm']:.4f}, EVM={p1_after['evm_percent']:.2f}%, offset={p1_after['pilot_offset']}")
    print(f"DELTA : Δrho={p1_after['rho_corr_norm']-p1_before['rho_corr_norm']:+.4f}, ΔEVM={p1_after['evm_percent']-p1_before['evm_percent']:+.2f}%")

    print("\n=== Wired (rx1) ↔ OTA (rx2) PSD Divergence (in-band) ===")
    print(f"BEFORE: JSD={w2_before['js_psd']:.4f}, KL={w2_before['kl_psd']:.4f}, kw={w2_before['kw']}, ko={w2_before['ko']}")
    print(f"AFTER : JSD={w2_after['js_psd']:.4f}, KL={w2_after['kl_psd']:.4f}, kw={w2_after['kw']}, ko={w2_after['ko']}")
    print(f"DELTA : ΔJSD={w2_after['js_psd']-w2_before['js_psd']:+.4f}, ΔKL={w2_after['kl_psd']-w2_before['kl_psd']:+.4f}")

    return p1_before, p1_after, w2_before, w2_after
# ---------- Pilot handling ----------
def find_pilot_offset(rx: np.ndarray, pilot: np.ndarray) -> int:
    """
    Coarse timing via correlation against full pilot waveform.
    Returns offset k where pilot best matches rx[k:k+len(pilot)].
    """
    corr = correlate(rx, np.conj(pilot), mode="valid")
    return int(np.argmax(np.abs(corr)))

def split_pulses(pilot: np.ndarray, thr: float = 1.0):
    """
    Split pilot into contiguous non-zero "pulses".
    thr: magnitude threshold to consider nonzero.
    Returns list of (start, end) indices.
    """
    mag = np.abs(pilot)
    nz = np.where(mag > thr)[0]
    if len(nz) == 0:
        raise ValueError("No pulses found in pilot.")
    segs = []
    s = nz[0]; p = nz[0]
    for idx in nz[1:]:
        if idx == p + 1:
            p = idx
        else:
            segs.append((s, p))
            s = idx; p = idx
    segs.append((s, p))
    return segs

def estimate_cfo_from_4pulse(rx_aligned: np.ndarray, pilot: np.ndarray, fs: float) -> float:
    """
    CFO from phase drift between pulses.
    For each pulse m, compute complex correlation h_m = <rx_pulse, pilot_pulse>.
    Phase(h_m) should drift linearly with pulse time if CFO exists.
    Fit slope -> CFO.
    """
    segs = split_pulses(pilot, thr=1.0)  # adjust thr if needed
    phases = []
    times = []
    for (a, b) in segs:
        rp = rx_aligned[a:b+1]
        pp = pilot[a:b+1]
        h = np.vdot(pp, rp)  # sum(conj(pp)*rp)
        phases.append(np.angle(h))
        # time at pulse center
        t_center = ((a + b) / 2.0) / fs
        times.append(t_center)

    phases = np.unwrap(np.array(phases))
    times = np.array(times)

    # linear fit: phase ≈ 2π*CFO*t + const
    slope = np.polyfit(times, phases, 1)[0]  # rad/sec
    cfo_hz = slope / (2*np.pi)
    return float(cfo_hz)

def correct_cfo(x: np.ndarray, cfo_hz: float, fs: float) -> np.ndarray:
    n = np.arange(len(x), dtype=np.float64)
    rot = np.exp(-1j * 2*np.pi * cfo_hz * n / fs)
    return x * rot.astype(np.complex64)

def correct_const_phase(rx_seg: np.ndarray, pilot: np.ndarray) -> np.ndarray:
    """
    Remove constant phase offset: rx_seg *= exp(-j*phi),
    where phi = angle(<pilot, rx_seg>).
    """
    phi = np.angle(np.vdot(pilot, rx_seg))
    return rx_seg * np.exp(-1j * phi).astype(np.complex64)

# ---------- Distributions ----------
def psd_dist(x: np.ndarray, fs: float, nperseg=8192):
    """
    Welch PSD (two-sided) -> normalized distribution over frequency bins.
    """
    f, Pxx = welch(x, fs=fs, nperseg=nperseg, return_onesided=False, scaling="density")
    idx = np.argsort(f)
    return f[idx], safe_prob(Pxx[idx])

def band_select(f, P, f_low, f_high):
    m = (f >= f_low) & (f <= f_high)
    return f[m], safe_prob(P[m])

# ---------- Main scoring ----------
def score_ota_vs_wired(wired: np.ndarray, ota: np.ndarray, pilot: np.ndarray, fs: float,
                       nperseg=8192, f_low=None, f_high=None):
    """
    Returns CFO estimate and KL/JSD scores between wired and OTA PSDs
    after pilot alignment + CFO/phase correction + RMS normalization.
    """
    # 1) Align pilot in each capture
    kw = find_pilot_offset(wired, pilot)
    ko = find_pilot_offset(ota, pilot)

    # 2) Grab pilot-length segments for CFO/phase estimate (OTA)
    ota_p = ota[ko:ko+len(pilot)]
    cfo = estimate_cfo_from_4pulse(ota_p, pilot, fs)

    # 3) CFO-correct whole OTA, then re-align segment and de-rotate constant phase
    ota_c = correct_cfo(ota, cfo, fs)
    ota_p2 = ota_c[ko:ko+len(pilot)]
    ota_p2 = correct_const_phase(ota_p2, pilot)

    # 4) Compare equal-length windows starting at pilot
    L = min(len(wired) - kw, len(ota_c) - ko)
    w_win = normalize_rms(wired[kw:kw+L])
    o_win = normalize_rms(ota_c[ko:ko+L])

    # 5) PSD distributions (optionally in-band)
    fW, PW = psd_dist(w_win, fs, nperseg=nperseg)
    fO, PO = psd_dist(o_win, fs, nperseg=nperseg)
    if f_low is not None and f_high is not None:
        fW, PW = band_select(fW, PW, f_low, f_high)
        fO, PO = band_select(fO, PO, f_low, f_high)

    if len(PW) != len(PO) or not np.allclose(fW, fO):
        raise RuntimeError("Frequency grids differ; keep same fs/nperseg and band limits.")

    return {
        "cfo_hz_est": cfo,
        "kl_psd_wired_to_ota": kl_div(PW, PO),
        "js_psd_wired_vs_ota": js_div(PW, PO),
    }

def find_pilot_offset(rx: np.ndarray, pilot: np.ndarray) -> int:
    corr = correlate(rx, np.conj(pilot), mode="valid")
    return int(np.argmax(np.abs(corr)))

def wired_vs_pilot_metrics(wired: np.ndarray, pilot: np.ndarray):
    """
    Returns: offset, normalized correlation rho, complex gain h, NMSE, EVM_rms, EVM_percent.
    """
    k = find_pilot_offset(wired, pilot)
    x = wired[k:k+len(pilot)]

    # Best-fit complex gain h (absorbs amplitude+phase)
    denom = np.vdot(pilot, pilot) + EPS
    h = np.vdot(pilot, x) / denom

    # Error + metrics
    e = x - h * pilot
    nmse = (np.vdot(e, e).real) / ((np.vdot(h*pilot, h*pilot).real) + EPS)
    evm_rms = np.sqrt(nmse)
    rho = np.abs(np.vdot(x, pilot)) / ((np.linalg.norm(x) * np.linalg.norm(pilot)) + EPS)

    return {
        "pilot_offset": k,
        "rho_corr_norm": float(rho),
        "h_gain": complex(h),
        "nmse": float(nmse),
        "evm_rms": float(evm_rms),
        "evm_percent": float(100*evm_rms),
    }

# ---------- Example ----------
if __name__ == "__main__":
    fs = 20e6
    wn = [100e3 / (FS / 2), 2e6 / (FS / 2)]
    filtering = 1

    base_dir = pick_directory("Pick the folder containing your IQ files")
    if base_dir is None:
        raise SystemExit("No folder selected.")

    pilot_path = base_dir / "pilot.iq"
    wired_path = base_dir / "rx1.iq"
    ota_path = base_dir / "rx2.iq"

    print("Using:")
    print(" pilot:", pilot_path)
    print(" wired:", wired_path)
    print(" ota  :", ota_path)
    pilot = read_iq_int16(pilot_path)
    wired = read_iq_int16(wired_path)
    ota   = read_iq_int16(ota_path)

    # Example: compare only ±2 MHz around DC (adjust to your occupied BW / center)

    run_all(
        pilot_path=pilot_path,
        rx1_path=wired_path,
        rx2_path=ota_path,
        wn=wn,
        filtering=filtering,
        MetaDataObj=MetaDataObj,
        filter_signal=filter_signal,
        f_low=-2e6,
        f_high=2e6
    )

    out = score_ota_vs_wired(wired, ota, pilot, fs,
                             nperseg=16384,
                             f_low=-2e6, f_high=2e6)

    print(out)
    wp = wired_vs_pilot_metrics(wired, pilot)

    print("=== Wired vs Pilot ===")
    print(f"Pilot offset (samples): {wp['pilot_offset']}")
    print(f"Normalized correlation ρ: {wp['rho_corr_norm']:.4f}")
    print(f"Gain h (complex): {wp['h_gain']}")
    print(f"NMSE: {wp['nmse']:.6e}")
    print(f"EVM RMS: {wp['evm_percent']:.2f}%")


