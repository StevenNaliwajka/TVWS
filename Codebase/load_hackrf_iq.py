import numpy as np

def load_hackrf_iq(path: str) -> np.ndarray:
    """
    Load HackRF .iq file (sc8: int8 interleaved I,Q) and return complex64 array.
    """
    raw = np.fromfile(path, dtype=np.int8)

    # Ensure even length (I,Q pairs)
    if len(raw) % 2 != 0:
        raw = raw[:-1]

    I = raw[0::2].astype(np.float32)
    Q = raw[1::2].astype(np.float32)

    # Optionally scale by 127 to get roughly [-1,1]
    I /= 127.0
    Q /= 127.0

    return I + 1j * Q
