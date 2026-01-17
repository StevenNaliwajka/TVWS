from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Defaults (edit these, not argparse)
# =============================================================================
DEFAULT_RUNS = 1000

DEFAULT_SAMPLE_RATE_HZ = 20_000_000
DEFAULT_CENTER_FREQ_HZ = 520_000_000
DEFAULT_NUM_SAMPLES = 7_000

DEFAULT_LNA_DB = 16
DEFAULT_VGA_DB = 16

# Per-RX defaults (used when you do NOT pass --lna/--vga and do NOT pass --rx*-lna/--rx*-vga)
DEFAULT_RX1_LNA_DB = 8
DEFAULT_RX1_VGA_DB = 8
DEFAULT_RX2_LNA_DB = 42
DEFAULT_RX2_VGA_DB = 42

DEFAULT_TX_AMP_DB = 42
DEFAULT_RF_AMP = True
DEFAULT_ANTENNA_POWER = False

DEFAULT_RX1_SERIAL = "0000000000000000930c64dc2a0a66c3"
DEFAULT_RX2_SERIAL = "000000000000000087c867dc2b54905f"
DEFAULT_TX1_SERIAL = "0000000000000000930c64dc292c35c3"

DEFAULT_TAG = ""
DEFAULT_SAFETY_MARGIN_S = 0
DEFAULT_RX_READY_TIMEOUT_S = 0.5
DEFAULT_TX_WAIT_TIMEOUT_S = 3
DEFAULT_MAX_RUN_RETRIES = 3
DEFAULT_RETRY_BACKOFF_S = 0.25

DEFAULT_HW_TRIGGER = True  # RX uses -H unless --no-hw-trigger is passed


# =============================================================================
# Data structure
# =============================================================================
@dataclass(frozen=True)
class RunConfig:
    runs: int
    sample_rate_hz: int
    freq_hz: int
    num_samples: int

    # "Global" RX gains (recorded for reference; may be overridden per-RX)
    lna_db: int
    vga_db: int

    # Effective per-RX gains actually used for capture
    rx1_lna_db: int
    rx1_vga_db: int
    rx2_lna_db: int
    rx2_vga_db: int

    rx1_serial: str
    rx2_serial: str
    tx_serial: str
    tx_amp_db: int
    rf_amp: bool
    antenna_power: bool
    pulse_path: str
    data_root: str
    tag: str
    config_path: Optional[str]
    safety_margin_s: float
    rx_ready_timeout_s: float
    tx_wait_timeout_s: float
    hw_trigger: bool

    # Retry behavior
    max_run_retries: int
    retry_backoff_s: float
