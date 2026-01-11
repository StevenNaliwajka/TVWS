#!/usr/bin/env python3
"""
make_pulse_iq.py

Generate a HackRF unsigned 8-bit interleaved IQ file (pulse.iq) containing:
  - 3 bursts at -2 MHz baseband offset
  - 1 burst at +2 MHz baseband offset

Notes on "seeing both -2 and +2":
A hard on/off (rectangular) burst creates wideband spectral splatter. If you are
inspecting a short-time FFT, that splatter can look like a smaller "image" at
other frequencies (including +2 MHz). To reduce that, we apply a smooth
raised-cosine (Tukey-like) ramp on burst edges (configurable via --ramp-ms).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple, List

import numpy as np


def _raised_cosine_envelope(n: int, ramp_n: int) -> np.ndarray:
    """0..1 envelope with raised-cosine ramps at both ends."""
    if n <= 0:
        return np.array([], dtype=np.float32)
    if ramp_n <= 0:
        return np.ones(n, dtype=np.float32)

    ramp_n = int(min(ramp_n, n // 2))
    env = np.ones(n, dtype=np.float32)

    # sin^2 ramp gives a smooth 0->1 with zero slope at endpoints.
    t = np.arange(ramp_n, dtype=np.float32) / float(ramp_n)
    ramp = np.sin(0.5 * np.pi * t) ** 2  # 0..1
    env[:ramp_n] = ramp
    env[-ramp_n:] = ramp[::-1]
    return env


def _tone_burst(freq_hz: float, n: int, fs: float, amp: float, ramp_n: int) -> np.ndarray:
    """Complex tone burst with optional raised-cosine ramp."""
    t = np.arange(n, dtype=np.float32) / float(fs)
    x = (amp * np.exp(1j * 2.0 * np.pi * float(freq_hz) * t)).astype(np.complex64)

    if ramp_n > 0:
        env = _raised_cosine_envelope(n, ramp_n).astype(np.float32, copy=False)
        x *= env.astype(np.complex64)
    return x


def _complex_to_hackrf_u8_iq(x: np.ndarray) -> np.ndarray:
    """
    Convert complex float IQ in [-1,1] to HackRF unsigned 8-bit interleaved IQ:
      I,Q,I,Q,... where I/Q are uint8 in [0,255] centered at 128.
    """
    x = x.astype(np.complex64, copy=False)

    I = np.clip(np.real(x), -1.0, 1.0)
    Q = np.clip(np.imag(x), -1.0, 1.0)

    u8_i = np.round((I * 127.0) + 128.0).astype(np.uint8)
    u8_q = np.round((Q * 127.0) + 128.0).astype(np.uint8)

    iq_u8 = np.empty(u8_i.size * 2, dtype=np.uint8)
    iq_u8[0::2] = u8_i
    iq_u8[1::2] = u8_q
    return iq_u8


def _bin_power_db(x: np.ndarray, fs_hz: float, f_hz: float) -> float:
    """Rough single-bin power estimate around f_hz (for quick verification prints)."""
    if x.size == 0:
        return float("-inf")

    # Use a Hann to reduce leakage in the diagnostic FFT.
    w = np.hanning(x.size).astype(np.float32)
    X = np.fft.fftshift(np.fft.fft((x * w).astype(np.complex64)))
    freqs = np.fft.fftshift(np.fft.fftfreq(x.size, d=1.0 / fs_hz))

    idx = int(np.argmin(np.abs(freqs - f_hz)))
    p = float(np.abs(X[idx]) ** 2)
    return 10.0 * np.log10(p + 1e-30)


def make_pulse_iq(
    out_path: str | Path = "Codebase/Collection/pulse.iq",
    fs_hz: float = 20_000_000,
    f1_hz: float = -2_000_000,
    f2_hz: float = 2_000_000,
    burst_ms: float = 2.0,
    gap_ms: float = 2.0,
    ramp_ms: float = 0.25,
    amp: float = 0.8,
    bursts_f1: int = 3,
    bursts_f2: int = 1,
    verify: bool = False,
) -> Tuple[Path, int, int]:
    """
    Build the burst pattern and write HackRF U8 IQ to disk.

    Returns:
      (out_path, bytes_written, iq_samples_written)
    """
    out_path = Path(out_path)

    if fs_hz <= 0:
        raise ValueError("fs_hz must be > 0")
    if burst_ms <= 0:
        raise ValueError("burst_ms must be > 0")
    if gap_ms < 0:
        raise ValueError("gap_ms must be >= 0")
    if ramp_ms < 0:
        raise ValueError("ramp_ms must be >= 0")
    if not (0.0 <= amp <= 1.0):
        raise ValueError("amp must be in [0, 1]")
    if bursts_f1 < 0 or bursts_f2 < 0:
        raise ValueError("bursts_f1 and bursts_f2 must be >= 0")

    burst_n = int(round(fs_hz * (burst_ms / 1000.0)))
    gap_n = int(round(fs_hz * (gap_ms / 1000.0)))
    ramp_n = int(round(fs_hz * (ramp_ms / 1000.0)))

    if burst_n <= 0:
        raise ValueError("Computed burst_n <= 0; increase burst_ms or fs_hz")

    # Prevent ramp from exceeding half the burst.
    ramp_n = int(min(ramp_n, burst_n // 2))

    sil = np.zeros(gap_n, dtype=np.complex64) if gap_n > 0 else None

    parts: List[np.ndarray] = []
    debug_bursts: List[np.ndarray] = []  # for optional verification

    # #1, #2, #3 at f1 (e.g. -2 MHz)
    for _ in range(bursts_f1):
        b = _tone_burst(f1_hz, burst_n, fs_hz, amp, ramp_n)
        parts.append(b)
        if verify:
            debug_bursts.append(b)
        if sil is not None and sil.size:
            parts.append(sil)

    # #4 (and any additional) at f2 (e.g. +2 MHz)
    for i in range(bursts_f2):
        b = _tone_burst(f2_hz, burst_n, fs_hz, amp, ramp_n)
        parts.append(b)
        if verify:
            debug_bursts.append(b)
        if i != bursts_f2 - 1 and sil is not None and sil.size:
            parts.append(sil)

    x = np.concatenate(parts) if parts else np.array([], dtype=np.complex64)

    if verify and debug_bursts:
        # Print per-burst tone dominance at +/-2 MHz
        print("[verify] Per-burst power estimate (dB, arbitrary):")
        for i, b in enumerate(debug_bursts, start=1):
            p_f1 = _bin_power_db(b, fs_hz, f1_hz)
            p_f2 = _bin_power_db(b, fs_hz, f2_hz)
            # 'Image suppression' from f1->f2 or f2->f1 depending on burst freq
            img = p_f2 - p_f1 if abs(f1_hz - f2_hz) > 0 else float('nan')
            print(f"  burst #{i:02d}: P(f1={f1_hz/1e6:+.1f}MHz)={p_f1:7.1f} dB, "
                  f"P(f2={f2_hz/1e6:+.1f}MHz)={p_f2:7.1f} dB, "
                  f"(P2-P1)={img:6.1f} dB")

    iq_u8 = _complex_to_hackrf_u8_iq(x)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    iq_u8.tofile(out_path)

    return out_path, int(iq_u8.size), int(x.size)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate pulse.iq with 3 bursts at -2 MHz and 1 burst at +2 MHz (no simultaneous tones)."

    )
    ap.add_argument("--out", default="Codebase/Collection/pulse.iq",
                    help="Output .iq path (HackRF unsigned 8-bit IQ).")
    ap.add_argument("--fs", type=float, default=20_000_000, help="Sample rate in Hz (default: 20e6).")
    ap.add_argument("--f1", type=float, default=-2_000_000, help="Baseband offset for first bursts (Hz).")
    ap.add_argument("--f2", type=float, default=2_000_000, help="Baseband offset for final burst(s) (Hz).")
    ap.add_argument("--burst-ms", type=float, default=2.0, help="Burst duration in milliseconds.")
    ap.add_argument("--gap-ms", type=float, default=2.0, help="Gap duration in milliseconds.")
    ap.add_argument("--ramp-ms", type=float, default=0.25,
                    help="Edge ramp (raised-cosine) in milliseconds (reduces spectral splatter). Use 0 for hard edges.")
    ap.add_argument("--amp", type=float, default=0.8, help="Amplitude 0..1 (default: 0.8).")
    ap.add_argument("--bursts-f1", type=int, default=3, help="Number of bursts at f1 (default: 3).")
    ap.add_argument("--bursts-f2", type=int, default=1, help="Number of bursts at f2 (default: 1).")
    ap.add_argument("--verify", action="store_true",
                    help="Print a quick per-burst power check at f1/f2 to confirm separation.")

    args = ap.parse_args()

    out_path, bytes_written, iq_samples = make_pulse_iq(
        out_path=args.out,
        fs_hz=args.fs,
        f1_hz=args.f1,
        f2_hz=args.f2,
        burst_ms=args.burst_ms,
        gap_ms=args.gap_ms,
        ramp_ms=args.ramp_ms,
        amp=args.amp,
        bursts_f1=args.bursts_f1,
        bursts_f2=args.bursts_f2,
        verify=args.verify,
    )

    print(f"Wrote {out_path}: {bytes_written} bytes, {iq_samples} IQ samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())