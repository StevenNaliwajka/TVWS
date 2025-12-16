def compute_tx_offset(meta_data) -> tuple[float, float]:
    """
    Returns (min_offset_hz, max_offset_hz) where offsets are relative to baseband_hz.
    Example: abs_freq 493e6, baseband 491e6 => offset +2e6.
    """
    base = float(meta_data.baseband_hz)
    f_sync = float(meta_data.sync_hz)
    f_tx = float(meta_data.signal_tx_hz)

    f_lo = min(f_sync, f_tx)
    f_hi = max(f_sync, f_tx)

    return (f_lo - base, f_hi - base)