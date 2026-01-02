
# Codebase/Calculations/compute_tx_offset.py
from __future__ import annotations

from typing import Iterable, Tuple


def compute_tx_offset(
    meta_data,
    tone_attrs: Iterable[str] = ("sync_hz", "signal_tx_hz"),
) -> Tuple[float, float]:
    """
    Return (min_off_hz, max_off_hz) offsets relative to baseband (DC).

    Offsets are computed as:
        off_hz = tone_hz - baseband_hz

    Notes:
    - If only one side exists (all offsets >= 0 or all <= 0), this function
      mirrors the magnitude to create a symmetric span about DC, so downstream
      filters still behave as expected.
    - Typical return: (-2e6, +2e6)

    Required:
      meta_data.baseband_hz
      and at least one of the tone attributes in `tone_attrs` must exist.
    """
    if not hasattr(meta_data, "baseband_hz"):
        raise AttributeError("meta_data must have attribute: baseband_hz")

    baseband_hz = float(getattr(meta_data, "baseband_hz"))

    offsets = []
    for attr in tone_attrs:
        if hasattr(meta_data, attr):
            tone_hz = float(getattr(meta_data, attr))
            offsets.append(tone_hz - baseband_hz)

    # Optional: allow a list/tuple of tones on the object as a fallback
    # (won't break anything if absent)
    if hasattr(meta_data, "tones_hz"):
        try:
            for tone_hz in getattr(meta_data, "tones_hz"):
                offsets.append(float(tone_hz) - baseband_hz)
        except TypeError:
            # tones_hz exists but isn't iterable; ignore it
            pass

    if not offsets:
        raise AttributeError(
            f"No tone frequencies found. Expected at least one of: {tuple(tone_attrs)} "
            f"(or meta_data.tones_hz)."
        )

    min_off = float(min(offsets))
    max_off = float(max(offsets))

    # If all tones are on one side of DC, mirror to make a usable +/- span.
    # This prevents downstream code from collapsing to a 0-width reference edge.
    if min_off >= 0.0 and max_off > 0.0:
        min_off = -max_off
    elif max_off <= 0.0 and min_off < 0.0:
        max_off = -min_off
    elif min_off == 0.0 and max_off == 0.0:
        # All tones exactly at baseband (unlikely, but handle)
        raise ValueError("All detected tones are at baseband (0 Hz offset); cannot infer span.")

    return min_off, max_off
