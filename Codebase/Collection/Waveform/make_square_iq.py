import numpy as np
from pathlib import Path


def generate_square_am_iq(
    sr=20_000_000,
    dur=0.0001,
    f_carrier=2_000_000,
    f_square=100_000,
    low_multiplier=2.0,   # <-- LOW lasts 2x longer than HIGH
    a_low=0.45,
    a_high=0.90,
    pad_samps=512,
):
    """
    Create complex IQ samples with square-wave amplitude envelope.

    low_multiplier:
        How much longer LOW lasts compared to HIGH.
        1.0 = 50/50
        2.0 = LOW twice as long as HIGH
    """

    # ---- derive duty automatically ----
    duty = 1.0 / (1.0 + low_multiplier)

    n = int(sr * dur)
    t = np.arange(n, dtype=np.float64) / sr

    # Square envelope
    phase = (t * f_square) % 1.0
    env = np.where(phase < duty, a_high, a_low).astype(np.float32)

    # Carrier tone
    carrier = np.exp(1j * 2 * np.pi * f_carrier * t).astype(np.complex64)

    iq = (env * carrier).astype(np.complex64)

    # Optional zero padding
    if pad_samps > 0:
        iq = np.concatenate([np.zeros(pad_samps, dtype=np.complex64), iq])

    return iq


def write_iq_file(iq, filename="square_50_100.iq"):
    """
    Save interleaved int8 IQ next to this script.
    """

    script_dir = Path(__file__).resolve().parent
    output_path = script_dir / filename

    iq8 = (
        np.column_stack((iq.real, iq.imag)) * 127.0
    ).astype(np.int8).ravel()

    iq8.tofile(output_path)

    print("Created IQ file:")
    print(f"  {output_path}")
    print(f"  Samples: {len(iq)}")


def run():
    iq = generate_square_am_iq(
        low_multiplier=2.0  # LOW time doubled
    )
    write_iq_file(iq)


if __name__ == "__main__":
    run()