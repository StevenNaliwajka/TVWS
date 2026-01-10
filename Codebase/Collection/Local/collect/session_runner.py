from __future__ import annotations
import argparse
import json
import shutil
import os
import random
import signal
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from Codebase.Collection.Local.tx.controller_lib import run_capture, CapturePaths
from Codebase.Collection.Local.util.subprocess_util import run_cmd_capture_text, require_tool
from Codebase.Collection.Local.util.hackrf_process import wait_hackrf_free, cleanup_hackrf_all, list_hackrf_transfer_procs
from Codebase.Collection.Local.run_report import generate_run_report

def _session_stamp() -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    return f"{ts}_{random.randint(1000, 9999)}"

@dataclass(frozen=True)
class SessionConfig:
    runs: int
    sample_rate: int
    freq: int
    lna: int
    vga: int
    num_samples: int
    rx1_serial: Optional[str]
    rx2_serial: Optional[str]
    tx_serial: Optional[str]
    data_root: Path
    tag: str

    # TX controller knobs
    amp: int = 45
    rf_amp: bool = True
    antenna_power: bool = False
    pulse: Path = Path("/opt/TVWS/Codebase/Collection/pilot.iq")
    safety_margin: float = 1.0
    rx_ready_timeout: float = 0.5
    tx_wait_timeout: float = 10.0
    hw_trigger: bool = True

def preflight_check_serials(rx1: Optional[str], rx2: Optional[str], tx: Optional[str]) -> None:
    if not (rx1 or rx2 or tx):
        return

    rc, out = run_cmd_capture_text(["hackrf_info"])
    if not out.strip():
        raise RuntimeError("hackrf_info returned no output. Is hackrf installed / accessible?")

    missing = []
    for label, s in [("RX1_SERIAL", rx1), ("RX2_SERIAL", rx2), ("TX_SERIAL", tx)]:
        if s and (s not in out):
            missing.append(f"{label} not found by hackrf_info: {s}")

    if missing:
        raise RuntimeError("; ".join(missing))


def build_user_config(cfg: SessionConfig, project_root: Path) -> dict:
    """
    Build a JSON-serializable dict of all user-managed knobs used for this session.
    This is what will be embedded into each per-run run_report.json.
    """
    return {
        "paths": {
            "project_root": str(project_root),
            "data_root": str(cfg.data_root),
            "pulse_path": str(cfg.pulse),
        },
        "session": {
            "runs": cfg.runs,
            "tag": cfg.tag,
        },
        "devices": {
            "mapping_mode": "serial",
            "rx_1": {"serial": cfg.rx1_serial, "index": None},
            "rx_2": {"serial": cfg.rx2_serial, "index": None},
            "tx": {"serial": cfg.tx_serial, "index": None},
        },
        "rf": {
            "center_freq_hz": cfg.freq,
            "sample_rate_hz": cfg.sample_rate,
            "num_samples": cfg.num_samples,
        },
        "rx_1": {
            "enabled": True,
            "lna_db": cfg.lna,
            "vga_db": cfg.vga,
            "capture_mode": "samples",
            "num_samples": cfg.num_samples,
            "output_pattern": "{prefix}_capture_1.iq",
            "log_filename": "rx1.log",
        },
        "rx_2": {
            "enabled": True,
            "lna_db": cfg.lna,
            "vga_db": cfg.vga,
            "capture_mode": "samples",
            "num_samples": cfg.num_samples,
            "output_pattern": "{prefix}_capture_2.iq",
            "log_filename": "rx2.log",
        },
        "tx": {
            "enabled": True,
            "txvga_db": cfg.amp,
            "rf_amp": cfg.rf_amp,
            "antenna_power": cfg.antenna_power,
            "pulse_path": str(cfg.pulse),
            "safety_margin": cfg.safety_margin,
            "rx_ready_timeout": cfg.rx_ready_timeout,
            "tx_wait_timeout": cfg.tx_wait_timeout,
            "hw_trigger": cfg.hw_trigger,
            "log_filename": "tx.log",
        },
    }

def run_session(cfg: SessionConfig, config_path: Optional[Path] = None) -> Path:
    # Preflight tools
    require_tool("hackrf_transfer")
    require_tool("hackrf_info")
    require_tool("python3")

    cfg.data_root.mkdir(parents=True, exist_ok=True)

    preflight_check_serials(cfg.rx1_serial, cfg.rx2_serial, cfg.tx_serial)

    ts = _session_stamp()
    session_name = f"collect_{ts}" + (f"_{cfg.tag}" if cfg.tag else "")
    session_dir = cfg.data_root / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    print(f"[local_collect.py] Data root   : {cfg.data_root}")
    print(f"[local_collect.py] Session dir : {session_dir}")
    print(f"[local_collect.py] Runs        : {cfg.runs}")
    print(f"[local_collect.py] Freq (Hz)   : {cfg.freq}")
    print(f"[local_collect.py] Sample rate : {cfg.sample_rate}")
    print(f"[local_collect.py] LNA/VGA     : {cfg.lna} / {cfg.vga}")
    print(f"[local_collect.py] Num samples : {cfg.num_samples}")
    print(f"[local_collect.py] Serials     : RX1={cfg.rx1_serial} RX2={cfg.rx2_serial} TX={cfg.tx_serial}")

    # Interrupt handler: cleanup stragglers by serial (ONLY those configured)
    serials = [cfg.rx1_serial, cfg.rx2_serial, cfg.tx_serial]

    def _handle_interrupt(signum, frame):
        print(f"[local_collect.py] Interrupt received; cleaning up hackrf_transfer processes...")
        cleanup_hackrf_all(serials)
        procs = list_hackrf_transfer_procs().strip()
        if procs:
            print("[local_collect.py] Remaining hackrf_transfer processes (if any):")
            print(procs)
        raise SystemExit(130)

    signal.signal(signal.SIGINT, _handle_interrupt)
    signal.signal(signal.SIGTERM, _handle_interrupt)

    for i in range(1, cfg.runs + 1):
        run_id = f"{i:04d}"
        run_dir = session_dir / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        print()
        print(f"[local_collect.py] ===== run_{run_id} / {cfg.runs} =====")
        print(f"[local_collect.py] Run dir: {run_dir}")
        print(f"[local_collect.py] Start  : {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")

        # Resource-busy guard
        if cfg.rx1_serial:
            wait_hackrf_free(cfg.rx1_serial, 0.5)
        if cfg.rx2_serial:
            wait_hackrf_free(cfg.rx2_serial, 0.5)
        if cfg.tx_serial:
            wait_hackrf_free(cfg.tx_serial, 0.5)

        prefix = f"{ts}_run_{run_id}"
        paths = CapturePaths(
            rx1_iq=run_dir / f"{prefix}_capture_1.iq",
            rx2_iq=run_dir / f"{prefix}_capture_2.iq",
            rx1_log=run_dir / "rx1.log",
            rx2_log=run_dir / "rx2.log",
            tx_log=run_dir / "tx.log",
        )

        rc = run_capture(
            paths=paths,
            freq=cfg.freq,
            sr=cfg.sample_rate,
            nsamples=cfg.num_samples,
            lna=cfg.lna,
            vga=cfg.vga,
            rx1_lna=None,
            rx1_vga=None,
            rx2_lna=None,
            rx2_vga=None,
            amp=cfg.amp,
            rf_amp=cfg.rf_amp,
            antenna_power=cfg.antenna_power,
            pulse=cfg.pulse,
            safety_margin=cfg.safety_margin,
            rx_ready_timeout=cfg.rx_ready_timeout,
            tx_wait_timeout=cfg.tx_wait_timeout,
            hw_trigger=cfg.hw_trigger,
            rx1_serial=cfg.rx1_serial,
            rx2_serial=cfg.rx2_serial,
            tx_serial=cfg.tx_serial,
        )

        # Post-run guard: if anything is still busy, cleanup (prevents Resource busy next loop)
        if cfg.rx1_serial and not wait_hackrf_free(cfg.rx1_serial, 0.8):
            print(f"[local_collect.py][WARN] RX1 still busy after run; cleaning up (serial={cfg.rx1_serial})")
            cleanup_hackrf_all([cfg.rx1_serial])
        if cfg.rx2_serial and not wait_hackrf_free(cfg.rx2_serial, 0.8):
            print(f"[local_collect.py][WARN] RX2 still busy after run; cleaning up (serial={cfg.rx2_serial})")
            cleanup_hackrf_all([cfg.rx2_serial])
        if cfg.tx_serial and not wait_hackrf_free(cfg.tx_serial, 0.8):
            print(f"[local_collect.py][WARN] TX still busy after run; cleaning up (serial={cfg.tx_serial})")
            cleanup_hackrf_all([cfg.tx_serial])

        print(f"[local_collect.py] End    : {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
        print(f"[local_collect.py] Exit code: {rc}")
        # Per-run report (JSON + TXT)
        # - Writes: run_report.json + run_report.txt
        # - If a --config-path was provided, snapshot it into the run folder and include it in the report
        # - Also embeds the *effective* values used for this run under report.extra.effective_config
        try:
            template_cfg = None
            if config_path and config_path.exists():
                try:
                    template_cfg = json.loads(config_path.read_text(encoding="utf-8"))
                except Exception as _e:
                    template_cfg = None
                try:
                    shutil.copy2(str(config_path), str(run_dir / "collection_config.json"))
                except Exception:
                    pass

            effective_cfg = build_user_config(cfg, project_root=Path.cwd())

            generate_run_report(
                run_dir=run_dir,
                config=(template_cfg or effective_cfg),
                config_path=config_path,
                extra={
                    "run_index": i,
                    "run_id": run_id,
                    "exit_code": rc,
                    "session_dir": str(session_dir),
                    "capture_prefix": prefix,
                    "template_loaded": (template_cfg is not None),
                    "effective_config": effective_cfg,
                },
                write_txt=True,
            )
        except Exception as e:
            print(f"[local_collect.py][WARN] Failed to write run report: {type(e).__name__}: {e}")

    print()
    print(f"[local_collect.py] Done. Session: {session_dir}")
    return session_dir

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="One-machine collection runner (3 HackRFs on same host).")

    ap.add_argument("--runs", type=int, default=1, help="Number of runs (default: 1)")
    ap.add_argument("--sample-rate", type=int, default=20_000_000, help="Sample rate (Hz)")
    ap.add_argument("--freq", type=int, default=520_000_000, help="Center frequency (Hz)")
    ap.add_argument("--lna", type=int, default=32, help="RX LNA gain")
    ap.add_argument("--vga", type=int, default=32, help="RX VGA gain")
    ap.add_argument("--num-samples", type=int, default=7_000, help="Number of IQ samples")

    ap.add_argument("--rx1-serial", default=None, help="HackRF serial for RX1")
    ap.add_argument("--rx2-serial", default=None, help="HackRF serial for RX2")
    ap.add_argument("--tx-serial", default=None, help="HackRF serial for TX")

    ap.add_argument("--data-root", default=None, help="Data output root (default: <PROJECT_ROOT>/Data)")
    ap.add_argument("--tag", default="", help="Optional tag appended to session folder name")
    ap.add_argument("--config-path", default=None, help="Path to user-managed config JSON (recorded in per-run reports)")

    # Optional advanced knobs (kept, but not required)
    ap.add_argument("--amp", type=int, default=45, help="TX amp (-x) (default: 45)")
    ap.add_argument("--rf-amp", dest="rf_amp", action="store_true")
    ap.add_argument("--no-rf-amp", dest="rf_amp", action="store_false")
    ap.set_defaults(rf_amp=True)

    ap.add_argument("--antenna-power", dest="antenna_power", action="store_true")
    ap.add_argument("--no-antenna-power", dest="antenna_power", action="store_false")
    ap.set_defaults(antenna_power=False)

    ap.add_argument("--pulse", default="/opt/TVWS/Codebase/Collection/pilot.iq", help="TX IQ file")
    ap.add_argument("--safety-margin", type=float, default=1.0)
    ap.add_argument("--rx-ready-timeout", type=float, default=0.5)
    ap.add_argument("--tx-wait-timeout", type=float, default=10.0)
    ap.add_argument("--no-hw-trigger", action="store_true")

    return ap

def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)

    # Default data root relative to repo root (assumes this file imported as a package)
    # The wrapper script will run this with correct working directory anyway.
    project_root = Path.cwd()
    data_root = Path(args.data_root).expanduser().resolve() if args.data_root else (project_root / "Data")
    resolved_config_path = Path(args.config_path).expanduser().resolve() if args.config_path else None

    cfg = SessionConfig(
        runs=args.runs,
        sample_rate=args.sample_rate,
        freq=args.freq,
        lna=args.lna,
        vga=args.vga,
        num_samples=args.num_samples,
        rx1_serial=args.rx1_serial,
        rx2_serial=args.rx2_serial,
        tx_serial=args.tx_serial,
        data_root=data_root,
        tag=args.tag,
        amp=args.amp,
        rf_amp=args.rf_amp,
        antenna_power=args.antenna_power,
        pulse=Path(args.pulse).expanduser().resolve(),
        safety_margin=args.safety_margin,
        rx_ready_timeout=args.rx_ready_timeout,
        tx_wait_timeout=args.tx_wait_timeout,
        hw_trigger=not args.no_hw_trigger,
    )

    run_session(cfg, config_path=resolved_config_path)
    return 0
