#!/usr/bin/env python3
from __future__ import annotations

"""
Single-file, one-machine HackRF collection runner.

Target repo path:
  Codebase/Collection/Local/local_collect.py

Typical usage:
  python3 Codebase/Collection/Local/local_collect.py --runs 100 \
    --rx1-serial ... --rx2-serial ... --tx-serial ...

Notes:
- This runner assumes 2 RX HackRFs + 1 TX HackRF on the SAME host.
- RX captures are launched via hackrf_transfer reads (optionally with -H hw-trigger).
- "READY" is inferred either from hackrf_transfer output patterns OR via a short fallback timeout.
"""

import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event, Thread, Timer
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

# ---- CLI Defaults (edit these, not the argparse calls) ----
# These defaults are used when you do NOT pass the flag on the command line.
#
# For serials, you can optionally set environment variables instead of passing args:
#   TVWS_RX1_SERIAL, TVWS_RX2_SERIAL, TVWS_TX_SERIAL




DEFAULT_RUNS = 1000
DEFAULT_SAMPLE_RATE_HZ = 20_000_000
DEFAULT_CENTER_FREQ_HZ = 520_000_000
DEFAULT_NUM_SAMPLES = 7_000

DEFAULT_LNA_DB = 32
DEFAULT_VGA_DB = 32

# Per-RX defaults (so *every* flag has a default value)
DEFAULT_RX1_LNA_DB = DEFAULT_LNA_DB
DEFAULT_RX1_VGA_DB = DEFAULT_VGA_DB
DEFAULT_RX2_LNA_DB = DEFAULT_LNA_DB
DEFAULT_RX2_VGA_DB = DEFAULT_VGA_DB

DEFAULT_ENABLE_RX1 = True
DEFAULT_ENABLE_RX2 = True

DEFAULT_TX_AMP_DB = 45
DEFAULT_RF_AMP = True
DEFAULT_ANTENNA_POWER = False

DEFAULT_PULSE_IQ = "/opt/TVWS/Codebase/Collection/pilot.iq"

DEFAULT_SAFETY_MARGIN_S = 1.0
DEFAULT_RX_READY_TIMEOUT_S = 0.5
DEFAULT_TX_WAIT_TIMEOUT_S = 10.0
DEFAULT_HW_TRIGGER = True  # RX uses -H unless you pass --no-hw-trigger

# Output defaults
DEFAULT_DATA_ROOT = "/opt/TVWS/Data"
DEFAULT_TAG = ""
DEFAULT_CONFIG_PATH = ""  # "" => treat as "not provided" in your runtime logic

# Ready patterns default (edit to match what your RX scripts print)
DEFAULT_READY_PATTERNS = [
    r"\barmed\b",
]

# Serial env-var names + fallback defaults (so *every* flag has a default value)
ENVVAR_RX1_SERIAL = "TVWS_RX1_SERIAL"
ENVVAR_RX2_SERIAL = "TVWS_RX2_SERIAL"
ENVVAR_TX_SERIAL  = "TVWS_TX_SERIAL"

DEFAULT_RX1_SERIAL = "0000000000000000930c64dc292c35c3"
DEFAULT_RX2_SERIAL = "000000000000000087c867dc2b54905f"
DEFAULT_TX_SERIAL  = "0000000000000000930c64dc2a0a66c3"



# --------------------------------------------------------------------------------------
# Bootstrap: ensure repo root on sys.path
# --------------------------------------------------------------------------------------

def _ensure_repo_root_on_syspath() -> Path:
    """
    Add repo root to sys.path so `import Codebase...` works even when running by path.
    Repo root is the folder that contains the `Codebase/` directory.
    """
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "Codebase").is_dir():
            root = parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return root

    # Fallback (shouldn't happen): assume <root>/Codebase/Collection/Local/local_collect.py
    root = here.parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


# --------------------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------------------

def utc_stamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _session_stamp() -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    return f"{ts}_{random.randint(1000, 9999)}"


# --------------------------------------------------------------------------------------
# Subprocess helpers
# --------------------------------------------------------------------------------------

def require_tool(tool: str) -> None:
    from shutil import which
    if which(tool) is None:
        raise RuntimeError(f"Required tool not found in PATH: {tool}")


def run_cmd_capture_text(cmd: List[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return p.returncode, p.stdout or ""
    except FileNotFoundError:
        return 127, f"[ERROR] Tool not found: {cmd[0]}"


# --------------------------------------------------------------------------------------
# HackRF process utils (busy checks + cleanup by serial)
# --------------------------------------------------------------------------------------

def list_hackrf_transfer_procs() -> str:
    try:
        p = subprocess.run(
            ["pgrep", "-fa", "hackrf_transfer"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return p.stdout or ""
    except FileNotFoundError:
        return ""


def _pgrep_serial(serial: str) -> bool:
    # Looks for "hackrf_transfer ... -d <serial>".
    try:
        p = subprocess.run(
            ["pgrep", "-fa", f"hackrf_transfer.*-d[[:space:]]*{serial}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return p.returncode == 0
    except FileNotFoundError:
        return False


def wait_hackrf_free(serial: Optional[str], timeout_s: float = 0.8) -> bool:
    if not serial:
        return True
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if not _pgrep_serial(serial):
            return True
        time.sleep(0.1)
    return not _pgrep_serial(serial)


def cleanup_hackrf_serial(serial: Optional[str]) -> None:
    if not serial:
        return
    try:
        subprocess.run(
            ["pkill", "-f", f"hackrf_transfer.*-d[[:space:]]*{serial}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return


def cleanup_hackrf_all(serials: List[Optional[str]]) -> None:
    for s in serials:
        cleanup_hackrf_serial(s)


# --------------------------------------------------------------------------------------
# Minimal run report writer
# --------------------------------------------------------------------------------------

def generate_run_report(
    *,
    run_dir: Path,
    config: Dict[str, Any],
    config_path: Optional[Path],
    extra: Optional[Dict[str, Any]] = None,
    write_txt: bool = True,
) -> None:
    """
    Writes:
      - run_report.json
      - run_report.txt (optional)
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "created_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_dir": str(run_dir),
        "config_path": str(config_path) if config_path else None,
        "config": config,
        "extra": extra or {},
        "files": {},
    }

    # Best-effort file inventory (sizes only)
    try:
        for p in sorted(run_dir.iterdir()):
            if p.is_file():
                try:
                    report["files"][p.name] = {"bytes": p.stat().st_size}
                except Exception:
                    report["files"][p.name] = {}
    except Exception:
        pass

    (run_dir / "run_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if write_txt:
        lines = []
        lines.append(f"Run report: {run_dir}")
        lines.append(f"Created (UTC): {report['created_utc']}")
        if extra:
            lines.append("")
            lines.append("Extra:")
            for k, v in extra.items():
                lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append("Config (top-level keys): " + ", ".join(sorted(config.keys())))
        lines.append("")
        lines.append("Files:")
        for name, meta in report["files"].items():
            b = meta.get("bytes")
            lines.append(f"  {name} ({b} bytes)" if b is not None else f"  {name}")
        (run_dir / "run_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------
# RF capture logic (RX1 + RX2 + TX) with readiness inference
# --------------------------------------------------------------------------------------

DEFAULT_READY_PATTERNS = [
    r"wait.*trigger",
    r"waiting.*trigger",
    r"trigger.*armed",
    r"\barmed\b",
]


def _compile_ready_patterns(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


@dataclass(frozen=True)
class CapturePaths:
    rx1_iq: Path
    rx2_iq: Path
    rx1_log: Path
    rx2_log: Path
    tx_log: Path


@dataclass(frozen=True)
class RxProcCfg:
    name: str
    outfile: Path
    log_path: Path
    serial: Optional[str]
    lna: int
    vga: int
    enabled: bool = True


def _tee_and_detect(proc: subprocess.Popen, log_path: Path, ready_event: Event, ready_regexes: List[re.Pattern]) -> None:
    """
    Read combined stdout/stderr, write to log, and set ready_event on match.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "wb") as lf:
        while True:
            chunk = proc.stdout.readline() if proc.stdout is not None else b""
            if chunk:
                lf.write(chunk)
                lf.flush()

                line = chunk.decode("utf-8", errors="replace").strip()
                if (not ready_event.is_set()) and any(r.search(line) for r in ready_regexes):
                    ready_event.set()

            if proc.poll() is not None:
                # drain remaining output
                if proc.stdout is not None:
                    rest = proc.stdout.read()
                    if rest:
                        lf.write(rest)
                        lf.flush()
                return


def _start_rx_hackrf_transfer(
    *,
    rx: RxProcCfg,
    freq_hz: int,
    sample_rate_hz: int,
    nsamples: int,
    hw_trigger: bool,
    ready_timeout_s: float,
    ready_regexes: List[re.Pattern],
) -> Tuple[subprocess.Popen, Event, Thread, Timer]:
    """
    Start an RX capture using hackrf_transfer and set ready_event when it appears "armed",
    OR after ready_timeout_s (even if silent).
    """
    cmd = [
        "hackrf_transfer",
        "-r", str(rx.outfile),
        "-n", str(nsamples),
        "-f", str(freq_hz),
        "-s", str(sample_rate_hz),
        "-l", str(rx.lna),
        "-g", str(rx.vga),
    ]
    if rx.serial:
        cmd += ["-d", rx.serial]
    if hw_trigger:
        cmd.append("-H")

    dev_msg = f" (serial={rx.serial})" if rx.serial else ""
    print(f"[{utc_stamp()}] START {rx.name}{dev_msg}: {' '.join(cmd)}", flush=True)
    print(f"[{utc_stamp()}] {rx.name} log: {rx.log_path}", flush=True)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
    except FileNotFoundError:
        raise RuntimeError("hackrf_transfer not found in PATH (require_tool should have caught this).")

    ready_event = Event()

    # Tee output + detect readiness patterns
    t = Thread(target=_tee_and_detect, args=(proc, rx.log_path, ready_event, ready_regexes), daemon=True)
    t.start()

    # Safety: if hackrf is silent, still declare ready after ready_timeout_s
    timer = Timer(ready_timeout_s, lambda: ready_event.set())
    timer.daemon = True
    timer.start()

    return proc, ready_event, t, timer


def _run_tx(
    *,
    pulse_iq: Path,
    freq_hz: int,
    sample_rate_hz: int,
    amp: int,
    rf_amp: bool,
    antenna_power: bool,
    tx_serial: Optional[str],
    tx_log: Path,
) -> int:
    cmd = [
        "hackrf_transfer",
        "-t", str(pulse_iq),
        "-f", str(freq_hz),
        "-s", str(sample_rate_hz),
        "-x", str(amp),
        "-a", "1" if rf_amp else "0",
        "-p", "1" if antenna_power else "0",
    ]
    if tx_serial:
        cmd += ["-d", tx_serial]

    dev_msg = f" (serial={tx_serial})" if tx_serial else ""
    print(f"[TX] Transmitting{dev_msg}: {' '.join(cmd)}", flush=True)

    tx_log.parent.mkdir(parents=True, exist_ok=True)
    with open(tx_log, "wb") as f:
        try:
            p = subprocess.run(cmd, check=False, stdout=f, stderr=subprocess.STDOUT)
            return p.returncode
        except FileNotFoundError:
            print("[TX][ERROR] hackrf_transfer not found in PATH.", file=sys.stderr, flush=True)
            return 127


def run_capture(
    *,
    paths: CapturePaths,
    freq_hz: int,
    sample_rate_hz: int,
    nsamples: int,
    rx1: RxProcCfg,
    rx2: RxProcCfg,
    hw_trigger: bool,
    ready_timeout_s: float,
    tx_wait_timeout_s: float,
    pulse_iq: Path,
    amp: int,
    rf_amp: bool,
    antenna_power: bool,
    tx_serial: Optional[str],
    safety_margin_s: float,
    ready_patterns: Optional[List[str]] = None,
) -> int:
    """
    One-shot capture:
      1) start RX1/RX2 hackrf_transfer reads
      2) wait for enabled RX READY
      3) run TX pulse
      4) wait for RX captures to finish (terminate if needed)

    Returns: 0 if TX rc==0 else TX rc.
    """
    require_tool("hackrf_transfer")

    base_dir = paths.rx1_iq.parent
    base_dir.mkdir(parents=True, exist_ok=True)

    ready_regexes = _compile_ready_patterns(ready_patterns or DEFAULT_READY_PATTERNS)

    procs: List[Tuple[RxProcCfg, subprocess.Popen]] = []
    ready_events: List[Tuple[RxProcCfg, Event]] = []
    timers: List[Timer] = []

    def _start_if_enabled(rx: RxProcCfg):
        if not rx.enabled:
            return
        proc, ev, _t, timer = _start_rx_hackrf_transfer(
            rx=rx,
            freq_hz=freq_hz,
            sample_rate_hz=sample_rate_hz,
            nsamples=nsamples,
            hw_trigger=hw_trigger,
            ready_timeout_s=ready_timeout_s,
            ready_regexes=ready_regexes,
        )
        procs.append((rx, proc))
        ready_events.append((rx, ev))
        timers.append(timer)

    _start_if_enabled(rx1)
    _start_if_enabled(rx2)

    if not ready_events:
        print("[TX][ERROR] No receivers enabled; nothing to do.", file=sys.stderr, flush=True)
        return 2

    # ---- Wait for READY ----
    print("[TX] Waiting for RX READY...", flush=True)
    t0 = time.monotonic()
    while True:
        if all(ev.is_set() for _, ev in ready_events):
            break

        # If any RX died early, bail with logs
        for rx, proc in procs:
            rc = proc.poll()
            if rc is not None:
                ev = next((e for r, e in ready_events if r.name == rx.name), None)
                if ev is not None and (not ev.is_set()):
                    print(
                        f"[TX][ERROR] {rx.name} exited before READY (rc={rc}). Check {rx.log_path}",
                        file=sys.stderr,
                        flush=True,
                    )
                    return 3

        if time.monotonic() - t0 > tx_wait_timeout_s:
            not_ready = [rx.name for rx, ev in ready_events if not ev.is_set()]
            print(f"[TX][ERROR] Timeout waiting for READY from: {', '.join(not_ready)}", file=sys.stderr, flush=True)
            print("[TX] Check rx1.log / rx2.log for what happened.", file=sys.stderr, flush=True)
            return 4

        time.sleep(0.01)

    print("[TX] RX READY. Triggering TX now...", flush=True)

    # ---- TX ----
    tx_rc = _run_tx(
        pulse_iq=pulse_iq,
        freq_hz=freq_hz,
        sample_rate_hz=sample_rate_hz,
        amp=amp,
        rf_amp=rf_amp,
        antenna_power=antenna_power,
        tx_serial=tx_serial,
        tx_log=paths.tx_log,
    )
    if tx_rc != 0:
        print(f"[TX][ERROR] TX hackrf_transfer exited with {tx_rc}", file=sys.stderr, flush=True)

    # ---- Wait for RX to finish ----
    capture_secs = nsamples / max(1, sample_rate_hz)
    wait_budget = capture_secs + safety_margin_s
    print(f"[TX] Waiting ~{wait_budget:.6f}s for RX captures to finish...", flush=True)

    deadline = time.monotonic() + wait_budget + 2.0  # extra grace
    for rx, proc in procs:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            rc = proc.wait(timeout=remaining)
            if rc != 0:
                print(f"[TX][WARN] {rx.name} exited with code {rc} (see {rx.log_path})", file=sys.stderr, flush=True)
        except subprocess.TimeoutExpired:
            print(f"[TX][WARN] {rx.name} still running after wait; terminating.", file=sys.stderr, flush=True)
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()

    for timer in timers:
        try:
            timer.cancel()
        except Exception:
            pass

    print("[TX] All done. Files saved:", flush=True)
    if rx1.enabled:
        print(f"  {paths.rx1_iq}", flush=True)
        print(f"  {paths.rx1_log}", flush=True)
    if rx2.enabled:
        print(f"  {paths.rx2_iq}", flush=True)
        print(f"  {paths.rx2_log}", flush=True)
    print(f"  {paths.tx_log}", flush=True)

    return 0 if tx_rc == 0 else tx_rc


# --------------------------------------------------------------------------------------
# Session runner (multi-run orchestration)
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionConfig:
    runs: int
    sample_rate_hz: int
    center_freq_hz: int
    num_samples: int

    # defaults
    lna_db: int
    vga_db: int

    # optional overrides per RX
    rx1_lna_db: Optional[int]
    rx1_vga_db: Optional[int]
    rx2_lna_db: Optional[int]
    rx2_vga_db: Optional[int]

    # enable/disable receivers
    rx1_enabled: bool
    rx2_enabled: bool

    # devices
    rx1_serial: Optional[str]
    rx2_serial: Optional[str]
    tx_serial: Optional[str]

    # output
    data_root: Path
    tag: str

    # TX knobs
    tx_amp_db: int
    rf_amp: bool
    antenna_power: bool
    pulse_iq: Path

    # timings
    safety_margin_s: float
    rx_ready_timeout_s: float
    tx_wait_timeout_s: float
    hw_trigger: bool

    # ready patterns
    ready_patterns: List[str]


def preflight_check_serials(rx1: Optional[str], rx2: Optional[str], tx: Optional[str]) -> None:
    if not (rx1 or rx2 or tx):
        return

    rc, out = run_cmd_capture_text(["hackrf_info"])
    if rc != 0:
        raise RuntimeError(f"hackrf_info failed (rc={rc}). Is hackrf installed / accessible?")
    if not out.strip():
        raise RuntimeError("hackrf_info returned no output. Is hackrf installed / accessible?")

    missing = []
    for label, s in [("RX1_SERIAL", rx1), ("RX2_SERIAL", rx2), ("TX_SERIAL", tx)]:
        if s and (s not in out):
            missing.append(f"{label} not found by hackrf_info: {s}")

    if missing:
        raise RuntimeError("; ".join(missing))


def build_user_config(cfg: SessionConfig, project_root: Path) -> Dict[str, Any]:
    return {
        "paths": {
            "project_root": str(project_root),
            "data_root": str(cfg.data_root),
            "pulse_path": str(cfg.pulse_iq),
        },
        "session": {
            "runs": cfg.runs,
            "tag": cfg.tag,
        },
        "devices": {
            "mapping_mode": "serial",
            "rx_1": {"serial": cfg.rx1_serial, "index": None, "enabled": cfg.rx1_enabled},
            "rx_2": {"serial": cfg.rx2_serial, "index": None, "enabled": cfg.rx2_enabled},
            "tx": {"serial": cfg.tx_serial, "index": None, "enabled": True},
        },
        "rf": {
            "center_freq_hz": cfg.center_freq_hz,
            "sample_rate_hz": cfg.sample_rate_hz,
            "num_samples": cfg.num_samples,
        },
        "rx_1": {
            "lna_db": cfg.rx1_lna_db if cfg.rx1_lna_db is not None else cfg.lna_db,
            "vga_db": cfg.rx1_vga_db if cfg.rx1_vga_db is not None else cfg.vga_db,
            "hw_trigger": cfg.hw_trigger,
            "ready_timeout_s": cfg.rx_ready_timeout_s,
            "ready_patterns": cfg.ready_patterns,
            "output_pattern": "{prefix}_capture_1.iq",
            "log_filename": "rx1.log",
        },
        "rx_2": {
            "lna_db": cfg.rx2_lna_db if cfg.rx2_lna_db is not None else cfg.lna_db,
            "vga_db": cfg.rx2_vga_db if cfg.rx2_vga_db is not None else cfg.vga_db,
            "hw_trigger": cfg.hw_trigger,
            "ready_timeout_s": cfg.rx_ready_timeout_s,
            "ready_patterns": cfg.ready_patterns,
            "output_pattern": "{prefix}_capture_2.iq",
            "log_filename": "rx2.log",
        },
        "tx": {
            "txvga_db": cfg.tx_amp_db,
            "rf_amp": cfg.rf_amp,
            "antenna_power": cfg.antenna_power,
            "pulse_path": str(cfg.pulse_iq),
            "safety_margin_s": cfg.safety_margin_s,
            "tx_wait_timeout_s": cfg.tx_wait_timeout_s,
            "hw_trigger": cfg.hw_trigger,
            "log_filename": "tx.log",
        },
    }


def run_session(cfg: SessionConfig, config_path: Optional[Path] = None) -> Path:
    require_tool("hackrf_transfer")
    require_tool("hackrf_info")

    cfg.data_root.mkdir(parents=True, exist_ok=True)
    preflight_check_serials(cfg.rx1_serial, cfg.rx2_serial, cfg.tx_serial)

    ts = _session_stamp()
    session_name = f"collect_{ts}" + (f"_{cfg.tag}" if cfg.tag else "")
    session_dir = cfg.data_root / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    project_root = _ensure_repo_root_on_syspath()

    print(f"[local_collect.py] Repo root  : {project_root}")
    print(f"[local_collect.py] Data root  : {cfg.data_root}")
    print(f"[local_collect.py] Session dir: {session_dir}")
    print(f"[local_collect.py] Runs       : {cfg.runs}")
    print(f"[local_collect.py] Freq (Hz)  : {cfg.center_freq_hz}")
    print(f"[local_collect.py] Sample rate: {cfg.sample_rate_hz}")
    print(f"[local_collect.py] Samples    : {cfg.num_samples}")
    print(f"[local_collect.py] RX1 enabled: {cfg.rx1_enabled} (serial={cfg.rx1_serial})")
    print(f"[local_collect.py] RX2 enabled: {cfg.rx2_enabled} (serial={cfg.rx2_serial})")
    print(f"[local_collect.py] TX serial  : {cfg.tx_serial}")

    serials = [cfg.rx1_serial, cfg.rx2_serial, cfg.tx_serial]

    def _handle_interrupt(signum, frame):
        print("[local_collect.py] Interrupt received; cleaning up hackrf_transfer processes...", flush=True)
        cleanup_hackrf_all(serials)
        procs = list_hackrf_transfer_procs().strip()
        if procs:
            print("[local_collect.py] Remaining hackrf_transfer processes (if any):", flush=True)
            print(procs, flush=True)
        raise SystemExit(130)

    signal.signal(signal.SIGINT, _handle_interrupt)
    signal.signal(signal.SIGTERM, _handle_interrupt)

    # Optional: load template config JSON to embed in reports
    template_cfg: Optional[Dict[str, Any]] = None
    if config_path and config_path.exists():
        try:
            template_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            template_cfg = None

    effective_cfg = build_user_config(cfg, project_root=project_root)

    for i in range(1, cfg.runs + 1):
        run_id = f"{i:04d}"
        run_dir = session_dir / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        print()
        print(f"[local_collect.py] ===== run_{run_id} / {cfg.runs} =====")
        print(f"[local_collect.py] Run dir: {run_dir}")
        print(f"[local_collect.py] Start  : {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")

        # Resource-busy guard (by serial only)
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

        rx1 = RxProcCfg(
            name="rx1",
            outfile=paths.rx1_iq,
            log_path=paths.rx1_log,
            serial=cfg.rx1_serial,
            lna=cfg.rx1_lna_db if cfg.rx1_lna_db is not None else cfg.lna_db,
            vga=cfg.rx1_vga_db if cfg.rx1_vga_db is not None else cfg.vga_db,
            enabled=cfg.rx1_enabled,
        )
        rx2 = RxProcCfg(
            name="rx2",
            outfile=paths.rx2_iq,
            log_path=paths.rx2_log,
            serial=cfg.rx2_serial,
            lna=cfg.rx2_lna_db if cfg.rx2_lna_db is not None else cfg.lna_db,
            vga=cfg.rx2_vga_db if cfg.rx2_vga_db is not None else cfg.vga_db,
            enabled=cfg.rx2_enabled,
        )

        rc = run_capture(
            paths=paths,
            freq_hz=cfg.center_freq_hz,
            sample_rate_hz=cfg.sample_rate_hz,
            nsamples=cfg.num_samples,
            rx1=rx1,
            rx2=rx2,
            hw_trigger=cfg.hw_trigger,
            ready_timeout_s=cfg.rx_ready_timeout_s,
            tx_wait_timeout_s=cfg.tx_wait_timeout_s,
            pulse_iq=cfg.pulse_iq,
            amp=cfg.tx_amp_db,
            rf_amp=cfg.rf_amp,
            antenna_power=cfg.antenna_power,
            tx_serial=cfg.tx_serial,
            safety_margin_s=cfg.safety_margin_s,
            ready_patterns=cfg.ready_patterns,
        )

        # Post-run guard: cleanup if device stayed busy (prevents "Resource busy" next loop)
        if cfg.rx1_serial and not wait_hackrf_free(cfg.rx1_serial, 0.8):
            print(f"[local_collect.py][WARN] RX1 still busy after run; cleaning up (serial={cfg.rx1_serial})")
            cleanup_hackrf_all([cfg.rx1_serial])
        if cfg.rx2_serial and not wait_hackrf_free(cfg.rx2_serial, 0.8):
            print(f"[local_collect.py][WARN] RX2 still busy after run; cleaning up (serial={cfg.rx2_serial})")
            cleanup_hackrf_all([cfg.rx2_serial])
        if cfg.tx_serial and not wait_hackrf_free(cfg.tx_serial, 0.8):
            print(f"[local_collect.py][WARN] TX still busy after run; cleaning up (serial={cfg.tx_serial})")
            cleanup_hackrf_all([cfg.tx_serial])

        print(f"[local_collect.py] End      : {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
        print(f"[local_collect.py] Exit code: {rc}")

        # Snapshot config path into run folder (best-effort)
        if config_path and config_path.exists():
            try:
                shutil.copy2(str(config_path), str(run_dir / "collection_config.json"))
            except Exception:
                pass

        # Per-run report
        try:
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




def _env_serial(name: str) -> Optional[str]:
    v = os.environ.get(name)
    v = v.strip() if isinstance(v, str) else v
    return v if v else None


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="One-machine collection runner (2 RX + 1 TX HackRF on same host).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Number of runs")
    ap.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE_HZ, help="Sample rate (Hz)")
    ap.add_argument("--freq", type=int, default=DEFAULT_CENTER_FREQ_HZ, help="Center frequency (Hz)")
    ap.add_argument("--num-samples", type=int, default=DEFAULT_NUM_SAMPLES, help="Number of IQ samples")

    # common RX gains + per-RX overrides (now with explicit defaults)
    ap.add_argument("--lna", type=int, default=DEFAULT_LNA_DB, help="Default RX LNA gain")
    ap.add_argument("--vga", type=int, default=DEFAULT_VGA_DB, help="Default RX VGA gain")

    ap.add_argument("--rx1-lna", type=int, default=DEFAULT_RX1_LNA_DB, help="RX1 LNA gain")
    ap.add_argument("--rx1-vga", type=int, default=DEFAULT_RX1_VGA_DB, help="RX1 VGA gain")
    ap.add_argument("--rx2-lna", type=int, default=DEFAULT_RX2_LNA_DB, help="RX2 LNA gain")
    ap.add_argument("--rx2-vga", type=int, default=DEFAULT_RX2_VGA_DB, help="RX2 VGA gain")

    ap.add_argument("--no-rx1", action="store_true", default=(not DEFAULT_ENABLE_RX1), help="Disable RX1 capture")
    ap.add_argument("--no-rx2", action="store_true", default=(not DEFAULT_ENABLE_RX2), help="Disable RX2 capture")

    # serials (env-var override, otherwise fallback default serials)
    ap.add_argument(
        "--rx1-serial",
        default=(_env_serial(ENVVAR_RX1_SERIAL) or DEFAULT_RX1_SERIAL),
        help=f"HackRF serial for RX1 (hackrf_transfer -d). Env override: {ENVVAR_RX1_SERIAL}",
    )
    ap.add_argument(
        "--rx2-serial",
        default=(_env_serial(ENVVAR_RX2_SERIAL) or DEFAULT_RX2_SERIAL),
        help=f"HackRF serial for RX2 (hackrf_transfer -d). Env override: {ENVVAR_RX2_SERIAL}",
    )
    ap.add_argument(
        "--tx-serial",
        default=(_env_serial(ENVVAR_TX_SERIAL) or DEFAULT_TX_SERIAL),
        help=f"HackRF serial for TX (hackrf_transfer -d). Env override: {ENVVAR_TX_SERIAL}",
    )

    # output
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT, help="Data output root")
    ap.add_argument("--tag", default=DEFAULT_TAG, help="Optional tag appended to session folder name")
    ap.add_argument("--config-path", default=DEFAULT_CONFIG_PATH, help="Path to user-managed config JSON")

    # TX knobs
    ap.add_argument("--amp", type=int, default=DEFAULT_TX_AMP_DB, help="TX amp (-x)")

    ap.add_argument("--rf-amp", dest="rf_amp", action="store_true")
    ap.add_argument("--no-rf-amp", dest="rf_amp", action="store_false")
    ap.set_defaults(rf_amp=DEFAULT_RF_AMP)

    ap.add_argument("--antenna-power", dest="antenna_power", action="store_true")
    ap.add_argument("--no-antenna-power", dest="antenna_power", action="store_false")
    ap.set_defaults(antenna_power=DEFAULT_ANTENNA_POWER)

    ap.add_argument("--pulse", default=DEFAULT_PULSE_IQ, help="TX IQ file")

    # timings
    ap.add_argument("--safety-margin", type=float, default=DEFAULT_SAFETY_MARGIN_S,
                    help="Extra seconds beyond capture time to wait")
    ap.add_argument("--rx-ready-timeout", type=float, default=DEFAULT_RX_READY_TIMEOUT_S,
                    help="Seconds before considering an RX 'ready' even if hackrf is silent")
    ap.add_argument("--tx-wait-timeout", type=float, default=DEFAULT_TX_WAIT_TIMEOUT_S,
                    help="Max seconds to wait for ALL enabled RX ready before TX")
    ap.add_argument("--no-hw-trigger", action="store_true", default=(not DEFAULT_HW_TRIGGER),
                    help="Disable HW trigger (-H) on RX")

    # readiness patterns
    ap.add_argument(
        "--ready-pattern",
        action="append",
        default=list(DEFAULT_READY_PATTERNS),
        help="Regex for 'armed' state from RX output (repeatable).",
    )

    ap.add_argument(
        "--list-devices",
        action="store_true",
        default=False,
        help="Print hackrf_info output (connected devices / serials) and exit.",
    )
    return ap



def main(argv: Optional[List[str]] = None) -> int:
    project_root = _ensure_repo_root_on_syspath()

    ap = build_arg_parser()
    args = ap.parse_args(argv)

    # Apply env var serial defaults (lets you omit serial args on the CLI)
    # Example:
    #   export TVWS_RX1_SERIAL=000...
    #   export TVWS_RX2_SERIAL=000...
    #   export TVWS_TX_SERIAL=000...
    if args.rx1_serial is None:
        args.rx1_serial = _env_serial(ENV_RX1_SERIAL)
    if args.rx2_serial is None:
        args.rx2_serial = _env_serial(ENV_RX2_SERIAL)
    if args.tx_serial is None:
        args.tx_serial = _env_serial(ENV_TX_SERIAL)

    if args.list_devices:
        rc, out = run_cmd_capture_text(["hackrf_info"])
        print(out, end="" if out.endswith("\n") else "\n")
        return rc

    data_root = Path(args.data_root).expanduser().resolve() if args.data_root else (project_root / "Data")
    config_path = Path(args.config_path).expanduser().resolve() if args.config_path else None

    cfg = SessionConfig(
        runs=args.runs,
        sample_rate_hz=args.sample_rate,
        center_freq_hz=args.freq,
        num_samples=args.num_samples,
        lna_db=args.lna,
        vga_db=args.vga,
        rx1_lna_db=args.rx1_lna,
        rx1_vga_db=args.rx1_vga,
        rx2_lna_db=args.rx2_lna,
        rx2_vga_db=args.rx2_vga,
        rx1_enabled=not args.no_rx1,
        rx2_enabled=not args.no_rx2,
        rx1_serial=args.rx1_serial,
        rx2_serial=args.rx2_serial,
        tx_serial=args.tx_serial,
        data_root=data_root,
        tag=args.tag,
        tx_amp_db=args.amp,
        rf_amp=args.rf_amp,
        antenna_power=args.antenna_power,
        pulse_iq=Path(args.pulse).expanduser().resolve(),
        safety_margin_s=args.safety_margin,
        rx_ready_timeout_s=args.rx_ready_timeout,
        tx_wait_timeout_s=args.tx_wait_timeout,
        hw_trigger=not args.no_hw_trigger,
        ready_patterns=list(args.ready_pattern) if args.ready_pattern else list(DEFAULT_READY_PATTERNS),
    )

    run_session(cfg, config_path=config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
