# Codebase/TOF/tof_utils.py

import math
from typing import Any, Optional, Tuple

from Codebase.Object.metadata_object import MetaDataObj
from Codebase.TOF.Type4.compute_tof import compute_tof


def _safe_float_local(x: Any) -> Optional[float]:
    # Local copy to avoid import cycles (TOF utils should stay light)
    try:
        v = float(x)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return None


def extract_tof_value(compute_tof_result: Any, signal_obj: Any) -> Tuple[Optional[float], str]:
    """
    Best-effort extraction of a TOF scalar + a unit label.
    We don't assume units; we infer when we can from common attribute names.

    Returns: (value, unit_string)
    """
    # 1) If compute_tof returned a scalar
    v = _safe_float_local(compute_tof_result)
    if v is not None:
        return v, "unknown"

    # 2) If compute_tof returned a dict-like
    if isinstance(compute_tof_result, dict):
        for k, unit in [
            ("tof_air", "ns"),
            ("tof_air_ns", "ns"),
            ("tof_ns", "ns"),
            ("tof", "unknown"),
            ("tof_ps", "ps"),
            ("tof_air_ps", "ps"),
            ("time_of_flight", "unknown"),
        ]:
            if k in compute_tof_result:
                v2 = _safe_float_local(compute_tof_result.get(k))
                if v2 is not None:
                    return v2, unit

    # 3) Look for attributes on the Signal object
    for attr, unit in [
        ("tof_air", "ns"),
        ("tof_air_ns", "ns"),
        ("tof_ns", "ns"),
        ("tof", "unknown"),
        ("tof_ps", "ps"),
        ("tof_air_ps", "ps"),
        ("time_of_flight", "unknown"),
    ]:
        if hasattr(signal_obj, attr):
            v3 = _safe_float_local(getattr(signal_obj, attr))
            if v3 is not None:
                return v3, unit

    return None, "unknown"


def call_compute_tof(metadata: MetaDataObj, signal_obj: Any, peaks: Any) -> Any:
    """
    Calls compute_tof(metadata, signal_obj, peaks) if supported,
    otherwise falls back to compute_tof(metadata, signal_obj) and
    attaches peaks to the signal object for downstream code.
    """
    try:
        return compute_tof(metadata, signal_obj, peaks)
    except TypeError:
        # Older signature: compute_tof(metadata, signal_obj)
        try:
            setattr(signal_obj, "peaks", peaks)
        except Exception:
            pass
        return compute_tof(metadata, signal_obj)
