import numpy as np
from pathlib import Path


def generate_square_am_iq(
    sr=20_000_000,
    dur=0.0001,
    f_carrier=2_000_000,
    f_square=100_000,
    duty=0.5,
    a_low=0.45,     # 50% level (above noise floor)
    a_high=0.90,    # 100% level
    pad_samps=512,
):
    """
    Create complex IQ samples with a square-wave amplitude envelope.
    Returns complex64 IQ array.
    """

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

    print(f"Created IQ file:")
    print(f"  {output_path}")
    print(f"  Samples: {len(iq)}")


def run():
    iq = generate_square_am_iq()
    write_iq_file(iq)


if __name__ == "__main__":
    run()