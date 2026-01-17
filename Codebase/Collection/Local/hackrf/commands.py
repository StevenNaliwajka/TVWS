from __future__ import annotations

from pathlib import Path


def build_rx_cmd(
    *,
    out_path: Path,
    serial: str,
    sample_rate_hz: int,
    freq_hz: int,
    num_samples: int,
    lna_db: int,
    vga_db: int,
    hw_trigger: bool,
) -> list[str]:
    cmd = [
        "hackrf_transfer",
        "-r", str(out_path),
        "-n", str(num_samples),
        "-f", str(freq_hz),
        "-s", str(sample_rate_hz),
        "-l", str(lna_db),
        "-g", str(vga_db),
        "-d", serial,
    ]
    if hw_trigger:
        cmd.append("-H")
    return cmd


def build_tx_cmd(
    *,
    iq_path: Path,
    serial: str,
    sample_rate_hz: int,
    freq_hz: int,
    amp_db: int,
    rf_amp: bool,
    antenna_power: bool,
) -> list[str]:
    cmd = [
        "hackrf_transfer",
        "-t", str(iq_path),
        "-f", str(freq_hz),
        "-s", str(sample_rate_hz),
        "-x", str(amp_db),
        "-d", serial,
        "-a", "1" if rf_amp else "0",
        "-p", "1" if antenna_power else "0",
    ]
    return cmd
