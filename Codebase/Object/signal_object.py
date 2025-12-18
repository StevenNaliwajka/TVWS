from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np


class Signal:
    """
    Container for a single captured signal + its metadata.
    """

    def __init__(self, iq: np.ndarray, distance: float, path: Union[str, Path]) -> None:
        # Normalize + validate
        if not isinstance(iq, np.ndarray):
            raise TypeError(f"iq must be a numpy.ndarray. Got: {type(iq)}")
        if iq.ndim != 1:
            raise ValueError(f"iq must be a 1D array. Got shape: {iq.shape}")
        if not np.iscomplexobj(iq):
            iq = iq.astype(np.float32) + 0j

        distance = float(distance)
        if distance < 0:
            raise ValueError(f"distance must be >= 0. Got: {distance}")

        path = Path(path)

        self.iq = iq
        self.distance = distance
        self.path = path
        self.tof = None
        self.tof_air = None
