#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

#=============================================================================
# Defaults (edit these, not the argparse calls)
# =============================================================================
DEFAULT_RUNS = 100

DEFAULT_SAMPLE_RATE_HZ = 20_000_000
DEFAULT_CENTER_FREQ_HZ = 520_000_000
DEFAULT_NUM_SAMPLES = 7_000

DEFAULT_LNA_DB = 16
DEFAULT_VGA_DB = 16

# Per-RX defaults (used when you do NOT pass --lna/--vga and do NOT pass --rx*-lna/--rx*-vga)
DEFAULT_RX1_LNA_DB = 16
DEFAULT_RX1_VGA_DB = 16
DEFAULT_RX2_LNA_DB = 32
DEFAULT_RX2_VGA_DB = 32

DEFAULT_TX_AMP_DB = 16
DEFAULT_RF_AMP = True
DEFAULT_ANTENNA_POWER = False

DEFAULT_RX1_SERIAL = "0000000000000000930c64dc2a0a66c3"
DEFAULT_RX2_SERIAL = "000000000000000087c867dc2b54905f"
DEFAULT_TX1_SERIAL = "0000000000000000930c64dc292c35c3"

DEFAULT_TAG = ""
DEFAULT_SAFETY_MARGIN_S = 0.0
DEFAULT_RX_READY_TIMEOUT_S = 0
DEFAULT_TX_WAIT_TIMEOUT_S = 3.0

DEFAULT_HW_TRIGGER = True  # RX uses -H unless --no-hw-trigger is passed


# =============================================================================
# Data structures
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


def parse_args() -> RunConfig:
    project_root = Path(__file__).resolve().parents[3]
    default_data_root = str((project_root / "Data").resolve())
    default_pulse = str((project_root / "Codebase" / "Collection" / "SolidPulse.iq").resolve())
    # default_pulse = str((project_root / "Codebase" / "Collection" / "pulse.iq").resolve())

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

    a = ap.parse_args()

    # Determine if the global --lna/--vga flags were explicitly set.
    # This lets per-RX defaults differ, while still allowing a single global override.
    argv = sys.argv[1:]
    lna_was_set = _flag_present(argv, "--lna")
    vga_was_set = _flag_present(argv, "--vga")

    # Effective per-RX gains (precedence):
    # 1) --rx*-lna/--rx*-vga if provided
    # 2) --lna/--vga if explicitly provided
    # 3) DEFAULT_RX*_LNA_DB / DEFAULT_RX*_VGA_DB
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
    )


# =============================================================================
# Helpers
# =============================================================================
def _now_stamp() -> str:
    # Example: 2026-01-10T20-18-33
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _unique_session_name(tag: str) -> str:
    # Unique value: timestamp + pid + last 4 digits of monotonic_ns
    # Keeps it readable and extremely unlikely to collide.
    suffix = f"{os.getpid()}_{(time.monotonic_ns() % 10_000):04d}"
    base = f"Collection_{_now_stamp()}_{suffix}"
    return f"{base}_{tag}" if tag else base


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


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"[ERROR] Required tool not found in PATH: {name}")
    return path


def _run_cmd_capture(cmd: list[str], timeout_s: float = 10.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def _check_hackrfs_present(serials: list[str]) -> None:
    # We keep this simple and robust: call hackrf_info and check serial strings.
    proc = _run_cmd_capture(["hackrf_info"], timeout_s=10.0)
    out = proc.stdout or ""
    missing = [s for s in serials if s not in out]
    if missing:
        print(out)
        raise SystemExit(
            "[ERROR] Not all expected HackRF serials were found via `hackrf_info`.\n"
            f"Missing: {missing}\n"
            "Check USB connections, permissions/udev rules, and that the serials are correct."
        )


def _popen_to_files(cmd: list[str], log_path: Path) -> subprocess.Popen:
    # Write combined stdout+stderr to a log file for post-mortem debugging.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    f = log_path.open("w", encoding="utf-8")
    # NOTE: We intentionally do not close f here; Popen owns it for the process lifetime.
    return subprocess.Popen(
        cmd,
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_log_text(
    log_path: Path,
    needles: list[str],
    timeout_s: float,
    min_delay_s: float = 0.0,
) -> bool:
    """
    Wait until any needle appears in log file. Returns True if found, else False.
    """
    deadline = time.time() + timeout_s
    if min_delay_s > 0:
        time.sleep(min_delay_s)

    last_size = -1
    while time.time() < deadline:
        try:
            if log_path.exists():
                size = log_path.stat().st_size
                # Only read when file grows.
                if size != last_size:
                    last_size = size
                    text = log_path.read_text(encoding="utf-8", errors="replace")
                    for n in needles:
                        if n in text:
                            return True
        except Exception:
            pass
        time.sleep(0.02)
    return False


def _terminate(proc: subprocess.Popen, name: str, wait_s: float = 1.0) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=wait_s)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# =============================================================================
# HackRF command builders
# =============================================================================
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
        "-r",
        str(out_path),
        "-n",
        str(num_samples),
        "-f",
        str(freq_hz),
        "-s",
        str(sample_rate_hz),
        "-l",
        str(lna_db),
        "-g",
        str(vga_db),
        "-d",
        serial,
    ]
    if hw_trigger:
        cmd.append("-H")  # Wait for trigger input :contentReference[oaicite:1]{index=1}
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
        "-t",
        str(iq_path),
        "-f",
        str(freq_hz),
        "-s",
        str(sample_rate_hz),
        "-x",
        str(amp_db),
        "-d",
        serial,
    ]
    if rf_amp:
        cmd.append("-a")  # enable RF amplifier (front-end amp)
        cmd.append("1")
    else:
        cmd.append("-a")
        cmd.append("0")

    if antenna_power:
        cmd.append("-p")  # antenna power
        cmd.append("1")
    else:
        cmd.append("-p")
        cmd.append("0")

    # IMPORTANT:
    # For hardware triggering: the triggered devices use -H;
    # the *triggering* HackRF does NOT need a special argument to output trigger. :contentReference[oaicite:2]{index=2}
    return cmd


# =============================================================================
# Main collection loop
# =============================================================================
def run_collection(cfg: RunConfig) -> Path:
    project_root = Path(__file__).resolve().parents[3]  # .../Codebase/Collection/Local/local_collect.py
    data_root = Path(cfg.data_root).resolve()
    pulse_path = Path(cfg.pulse_path).resolve()

    session_dir = data_root / _unique_session_name(cfg.tag)
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save config snapshot for reproducibility
    (session_dir / "session_config.json").write_text(
        json.dumps(asdict(cfg), indent=2),
        encoding="utf-8",
    )

    print(f"[INFO] Project root : {project_root}")
    print(f"[INFO] Data root    : {data_root}")
    print(f"[INFO] Pulse IQ     : {pulse_path}")
    print(f"[INFO] Session dir  : {session_dir}")
    print(f"[INFO] Runs         : {cfg.runs}")
    print(f"[INFO] HW trigger   : {cfg.hw_trigger}")
    print(f"[INFO] RX gains     : global LNA/VGA={cfg.lna_db}/{cfg.vga_db}  |  RX1={cfg.rx1_lna_db}/{cfg.rx1_vga_db}  RX2={cfg.rx2_lna_db}/{cfg.rx2_vga_db}")

    if not pulse_path.exists():
        raise SystemExit(f"[ERROR] Pulse IQ file not found: {pulse_path}")

    # Sanity: tools + hardware presence
    _require_tool("hackrf_transfer")
    _require_tool("hackrf_info")
    _check_hackrfs_present([cfg.rx1_serial, cfg.rx2_serial, cfg.tx_serial])

    for i in range(1, cfg.runs + 1):
        run_name = f"run_{i:04d}"
        run_dir = session_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        rx1_iq = run_dir / "rx1.iq"
        rx2_iq = run_dir / "rx2.iq"

        rx1_log = run_dir / "rx1.log"
        rx2_log = run_dir / "rx2.log"
        tx_log = run_dir / "tx.log"

        print(f"\n[INFO] ===== {run_name} / {cfg.runs} =====")
        print(f"[INFO] Run dir: {run_dir}")

        rx1_cmd = build_rx_cmd(
            out_path=rx1_iq,
            serial=cfg.rx1_serial,
            sample_rate_hz=cfg.sample_rate_hz,
            freq_hz=cfg.freq_hz,
            num_samples=cfg.num_samples,
            lna_db=cfg.rx1_lna_db,
            vga_db=cfg.rx1_vga_db,
            hw_trigger=cfg.hw_trigger,
        )
        rx2_cmd = build_rx_cmd(
            out_path=rx2_iq,
            serial=cfg.rx2_serial,
            sample_rate_hz=cfg.sample_rate_hz,
            freq_hz=cfg.freq_hz,
            num_samples=cfg.num_samples,
            lna_db=cfg.rx2_lna_db,
            vga_db=cfg.rx2_vga_db,
            hw_trigger=cfg.hw_trigger,
        )
        tx_cmd = build_tx_cmd(
            iq_path=pulse_path,
            serial=cfg.tx_serial,
            sample_rate_hz=cfg.sample_rate_hz,
            freq_hz=cfg.freq_hz,
            amp_db=cfg.tx_amp_db,
            rf_amp=cfg.rf_amp,
            antenna_power=cfg.antenna_power,
        )

        print("[INFO] RX1 cmd:", " ".join(rx1_cmd))
        print("[INFO] RX2 cmd:", " ".join(rx2_cmd))
        print("[INFO] TX  cmd:", " ".join(tx_cmd))

        # Start receivers first (triggered mode will wait) :contentReference[oaicite:3]{index=3}
        rx1 = _popen_to_files(rx1_cmd, rx1_log)
        rx2 = _popen_to_files(rx2_cmd, rx2_log)

        try:
            if cfg.hw_trigger:
                # Wait until both RX logs show "Waiting for trigger" (or "READY" in some builds).
                # We also enforce at least rx_ready_timeout_s delay before we allow TX to start.
                needles = ["Waiting for trigger", "READY"]
                ok1 = _wait_for_log_text(
                    rx1_log,
                    needles=needles,
                    timeout_s=cfg.tx_wait_timeout_s,
                    min_delay_s=cfg.rx_ready_timeout_s,
                )
                ok2 = _wait_for_log_text(
                    rx2_log,
                    needles=needles,
                    timeout_s=cfg.tx_wait_timeout_s,
                    min_delay_s=0.0,
                )
                if not (ok1 and ok2):
                    raise RuntimeError(
                        "RX did not reach 'Waiting for trigger' state in time. "
                        "Check trigger wiring and that RX is started with -H."
                    )
            else:
                # Non-trigger mode: just give RX a tiny head start.
                time.sleep(cfg.rx_ready_timeout_s)

            # Start TX (this should trigger the -H receivers) :contentReference[oaicite:4]{index=4}
            tx = _popen_to_files(tx_cmd, tx_log)

            # Wait for TX to finish (it ends when IQ file is done streaming)
            try:
                tx.wait(timeout=cfg.tx_wait_timeout_s)
            except subprocess.TimeoutExpired:
                raise RuntimeError("TX did not finish in time (tx_wait_timeout exceeded).")

            if tx.returncode != 0:
                raise RuntimeError(f"TX failed (return code {tx.returncode}). See: {tx_log}")

            # RX should finish quickly after trigger, but allow some slack.
            rx_deadline = max(2.0, cfg.safety_margin_s + 2.0)
            try:
                rx1.wait(timeout=rx_deadline)
                rx2.wait(timeout=rx_deadline)
            except subprocess.TimeoutExpired:
                raise RuntimeError("RX did not finish in time after TX. Check trigger wiring.")

            if rx1.returncode != 0:
                raise RuntimeError(f"RX1 failed (return code {rx1.returncode}). See: {rx1_log}")
            if rx2.returncode != 0:
                raise RuntimeError(f"RX2 failed (return code {rx2.returncode}). See: {rx2_log}")

        except Exception as e:
            print(f"[ERROR] {run_name}: {e}")
            _terminate(rx1, "rx1")
            _terminate(rx2, "rx2")
            # If tx exists, terminate as well
            try:
                _terminate(tx, "tx")  # type: ignore[name-defined]
            except Exception:
                pass
            # Leave logs in place and stop the whole session:
            raise SystemExit(1)

        # Quick sanity: files should be non-empty
        rx1_size = rx1_iq.stat().st_size if rx1_iq.exists() else 0
        rx2_size = rx2_iq.stat().st_size if rx2_iq.exists() else 0
        print(f"[INFO] RX1 IQ bytes: {rx1_size}")
        print(f"[INFO] RX2 IQ bytes: {rx2_size}")

        if rx1_size == 0 or rx2_size == 0:
            print(
                "[WARN] One or both RX files are empty.\n"
                "       If you are using -H, this usually means the trigger was never received.\n"
                "       Check wiring between TX trigger-out and RX trigger-in."
            )

    print(f"\n[INFO] Done. Session saved at: {session_dir}")
    return session_dir





def main() -> int:
    cfg = parse_args()
    run_collection(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())