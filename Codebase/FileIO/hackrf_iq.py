# Codebase/FileIO/hackrf_iq.py

from pathlib import Path
from typing import Any

import numpy as np


def load_hackrf_iq_file(path: Path, meta_data: Any) -> np.ndarray:
    """Load a HackRF-style interleaved I/Q byte file into complex64 array."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    # Default assumptions: signed int8 interleaved I,Q
    dtype_name = getattr(meta_data, "iq_dtype", None) or getattr(meta_data, "iq_sample_dtype", None) or "int8"
    dtype_name = str(dtype_name).lower()

    if "uint8" in dtype_name:
        raw = np.fromfile(p, dtype=np.uint8).astype(np.int16) - 128
    else:
        raw = np.fromfile(p, dtype=np.int8).astype(np.int16)

    if raw.size < 2:
        return np.zeros((0,), dtype=np.complex64)

    if raw.size % 2 == 1:
        raw = raw[:-1]

    i = raw[0::2].astype(np.float32)
    q = raw[1::2].astype(np.float32)

    # Scale to roughly [-1, 1]
    scale = float(getattr(meta_data, "iq_scale", 1.0 / 128.0))
    i *= scale
    q *= scale

    return (i + 1j * q).astype(np.complex64)
