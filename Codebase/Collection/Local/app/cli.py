from __future__ import annotations

import argparse
import sys
from pathlib import Path

from Codebase.Collection.Local.app.config import (
    DEFAULT_ANTENNA_POWER,
    DEFAULT_CENTER_FREQ_HZ,
    DEFAULT_HW_TRIGGER,
    DEFAULT_LNA_DB,
    DEFAULT_MAX_RUN_RETRIES,
    DEFAULT_NUM_SAMPLES,
    DEFAULT_RETRY_BACKOFF_S,
    DEFAULT_RF_AMP,
    DEFAULT_RUNS,
    DEFAULT_RX1_LNA_DB,
    DEFAULT_RX1_SERIAL,
    DEFAULT_RX1_VGA_DB,
    DEFAULT_RX2_LNA_DB,
    DEFAULT_RX2_SERIAL,
    DEFAULT_RX2_VGA_DB,
    DEFAULT_RX_READY_TIMEOUT_S,
    DEFAULT_SAFETY_MARGIN_S,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_TAG,
    DEFAULT_TX1_SERIAL,
    DEFAULT_TX_AMP_DB,
    DEFAULT_TX_WAIT_TIMEOUT_S,
    DEFAULT_VGA_DB,
    RunConfig,
)


def _flag_present(argv: list[str], *names: str) -> bool:
    """
    Return True if any of the flags in `names` was explicitly present in argv.
    Supports both: --flag value  and  --flag=value
    """
    for n in names:
        if n in argv:
            return True
        prefix = n + "="
        if any(a.startswith(prefix) for a in argv):
            return True
    return False


def parse_args() -> RunConfig:
    project_root = Path(__file__).resolve().parents[3]
    default_data_root = str((project_root / "Data").resolve())
    default_pulse = str((project_root / "Codebase" / "Collection" / "pilot.iq").resolve())

    ap = argparse.ArgumentParser("local_collect.py")
    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Number of runs")
    ap.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE_HZ, help="Sample rate (Hz)")
    ap.add_argument("--freq", type=int, default=DEFAULT_CENTER_FREQ_HZ, help="Center frequency (Hz)")
    ap.add_argument("--lna", type=int, default=DEFAULT_LNA_DB, help="RX LNA gain (dB)")
    ap.add_argument("--vga", type=int, default=DEFAULT_VGA_DB, help="RX VGA gain (dB)")
    ap.add_argument("--rx1-lna", type=int, default=None, help="Override RX1 LNA gain (dB)")
    ap.add_argument("--rx1-vga", type=int, default=None, help="Override RX1 VGA gain (dB)")
    ap.add_argument("--rx2-lna", type=int, default=None, help="Override RX2 LNA gain (dB)")
    ap.add_argument("--rx2-vga", type=int, default=None, help="Override RX2 VGA gain (dB)")
    ap.add_argument("--num-samples", type=int, default=DEFAULT_NUM_SAMPLES, help="Number of IQ samples")

    ap.add_argument("--rx1-serial", default=DEFAULT_RX1_SERIAL, help="HackRF serial for RX1")
    ap.add_argument("--rx2-serial", default=DEFAULT_RX2_SERIAL, help="HackRF serial for RX2")
    ap.add_argument("--tx-serial", default=DEFAULT_TX1_SERIAL, help="HackRF serial for TX")

    ap.add_argument("--data-root", default=default_data_root, help="Data output root")
    ap.add_argument("--tag", default=DEFAULT_TAG, help="Optional tag appended to session folder name")
    ap.add_argument("--config-path", default=None, help="Optional config JSON path (recorded only)")

    ap.add_argument("--amp", type=int, default=DEFAULT_TX_AMP_DB, help="TX amp (-x)")
    ap.add_argument("--rf-amp", dest="rf_amp", action="store_true")
    ap.add_argument("--no-rf-amp", dest="rf_amp", action="store_false")
    ap.set_defaults(rf_amp=DEFAULT_RF_AMP)

    ap.add_argument("--antenna-power", dest="antenna_power", action="store_true")
    ap.add_argument("--no-antenna-power", dest="antenna_power", action="store_false")
    ap.set_defaults(antenna_power=DEFAULT_ANTENNA_POWER)

    ap.add_argument("--pulse", default=default_pulse, help="TX IQ file path")
    ap.add_argument("--safety-margin", type=float, default=DEFAULT_SAFETY_MARGIN_S)
    ap.add_argument("--rx-ready-timeout", type=float, default=DEFAULT_RX_READY_TIMEOUT_S)
    ap.add_argument("--tx-wait-timeout", type=float, default=DEFAULT_TX_WAIT_TIMEOUT_S)
    ap.add_argument("--no-hw-trigger", action="store_true", help="Disable hardware trigger (-H) on RX")

    ap.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RUN_RETRIES,
                    help="Max attempts per run before aborting the session")
    ap.add_argument("--retry-backoff", type=float, default=DEFAULT_RETRY_BACKOFF_S,
                    help="Seconds to sleep between attempts")

    a = ap.parse_args()

    argv = sys.argv[1:]
    lna_was_set = _flag_present(argv, "--lna")
    vga_was_set = _flag_present(argv, "--vga")

    rx1_lna = a.rx1_lna if a.rx1_lna is not None else (a.lna if lna_was_set else DEFAULT_RX1_LNA_DB)
    rx1_vga = a.rx1_vga if a.rx1_vga is not None else (a.vga if vga_was_set else DEFAULT_RX1_VGA_DB)
    rx2_lna = a.rx2_lna if a.rx2_lna is not None else (a.lna if lna_was_set else DEFAULT_RX2_LNA_DB)
    rx2_vga = a.rx2_vga if a.rx2_vga is not None else (a.vga if vga_was_set else DEFAULT_RX2_VGA_DB)

    return RunConfig(
        runs=a.runs,
        sample_rate_hz=a.sample_rate,
        freq_hz=a.freq,
        num_samples=a.num_samples,
        lna_db=a.lna,
        vga_db=a.vga,
        rx1_lna_db=int(rx1_lna),
        rx1_vga_db=int(rx1_vga),
        rx2_lna_db=int(rx2_lna),
        rx2_vga_db=int(rx2_vga),
        rx1_serial=a.rx1_serial,
        rx2_serial=a.rx2_serial,
        tx_serial=a.tx_serial,
        tx_amp_db=a.amp,
        rf_amp=bool(a.rf_amp),
        antenna_power=bool(a.antenna_power),
        pulse_path=str(a.pulse),
        data_root=str(a.data_root),
        tag=str(a.tag),
        config_path=a.config_path,
        safety_margin_s=float(a.safety_margin),
        rx_ready_timeout_s=float(a.rx_ready_timeout),
        tx_wait_timeout_s=float(a.tx_wait_timeout),
        hw_trigger=(DEFAULT_HW_TRIGGER and (not a.no_hw_trigger)),
        max_run_retries=int(a.max_retries),
        retry_backoff_s=float(a.retry_backoff),
    )
