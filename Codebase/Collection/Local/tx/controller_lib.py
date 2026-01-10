from __future__ import annotations
import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from typing import Optional, Tuple, List

from Codebase.Collection.Local.util.timeutil import utc_timestamp_for_filename
from Codebase.Collection.Local.util.subprocess_util import require_tool, run_cmd_capture_text

@dataclass(frozen=True)
class CapturePaths:
    rx1_iq: Path
    rx2_iq: Path
    rx1_log: Path
    rx2_log: Path
    tx_log: Optional[Path] = None

@dataclass(frozen=True)
class RxProc:
    name: str
    rx_py: Path
    outfile: Path
    log_path: Path
    serial: Optional[str]
    lna: int
    vga: int

def list_hackrf_devices() -> int:
    rc, out = run_cmd_capture_text(["hackrf_info"])
    print(out, end="" if out.endswith("\n") else "\n")
    return rc

def _tee_and_detect_ready(proc: subprocess.Popen, log_path: Path, ready_event: Event) -> None:
    '''
    Reads stdout, writes to log, sets ready_event when it sees an exact 'READY' line.
    '''
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "wb") as lf:
        while True:
            chunk = proc.stdout.readline() if proc.stdout is not None else b""
            if chunk:
                lf.write(chunk)
                lf.flush()

                line = chunk.decode("utf-8", errors="replace").strip()
                if line == "READY":
                    ready_event.set()

            if proc.poll() is not None:
                # drain remaining output
                if proc.stdout is not None:
                    rest = proc.stdout.read()
                    if rest:
                        lf.write(rest)
                        lf.flush()
                return

def start_local_rx(rx: RxProc, freq: int, sr: int, nsamples: int, hw_trigger: bool,
                   ready_timeout_s: float) -> Tuple[subprocess.Popen, Event, Thread]:
    cmd = [
        "python3", "-u",
        str(rx.rx_py),
        "--outfile", str(rx.outfile),
        "--freq", str(freq),
        "--sr", str(sr),
        "--nsamples", str(nsamples),
        "--lna", str(rx.lna),
        "--vga", str(rx.vga),
        "--ready-timeout", str(ready_timeout_s),
    ]
    if hw_trigger:
        cmd.append("--hw-trigger")
    if rx.serial:
        cmd += ["--serial", rx.serial]

    print(f"[TX] Starting {rx.name}: {' '.join(cmd)}")
    print(f"[TX] {rx.name} log: {rx.log_path}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,  # we read to detect READY
        stderr=subprocess.STDOUT,
        bufsize=0,
    )

    ready_event = Event()
    t = Thread(target=_tee_and_detect_ready, args=(proc, rx.log_path, ready_event), daemon=True)
    t.start()
    return proc, ready_event, t

def run_local_tx(pulse_iq: Path, freq: int, sr: int, amp: int, rf_amp: bool,
                 antenna_power: bool, tx_serial: Optional[str], tx_log: Optional[Path]) -> int:
    cmd = [
        "hackrf_transfer",
        "-t", str(pulse_iq),
        "-f", str(freq),
        "-s", str(sr),
        "-x", str(amp),
        "-a", "1" if rf_amp else "0",
        "-p", "1" if antenna_power else "0",
    ]
    if tx_serial:
        cmd += ["-d", tx_serial]

    dev_msg = f" (serial={tx_serial})" if tx_serial else ""
    print(f"[TX] Transmitting{dev_msg}: {' '.join(cmd)}")

    try:
        if tx_log:
            tx_log.parent.mkdir(parents=True, exist_ok=True)
            with open(tx_log, "wb") as f:
                p = subprocess.run(cmd, check=False, stdout=f, stderr=subprocess.STDOUT)
                return p.returncode
        else:
            p = subprocess.run(cmd, check=False)
            return p.returncode
    except FileNotFoundError:
        print("[TX][ERROR] hackrf_transfer not found in PATH.", file=sys.stderr)
        return 127

def run_capture(
    *,
    paths: CapturePaths,
    freq: int,
    sr: int,
    nsamples: int,
    lna: int,
    vga: int,
    rx1_lna: Optional[int],
    rx1_vga: Optional[int],
    rx2_lna: Optional[int],
    rx2_vga: Optional[int],
    amp: int,
    rf_amp: bool,
    antenna_power: bool,
    pulse: Path,
    safety_margin: float,
    rx_ready_timeout: float,
    tx_wait_timeout: float,
    hw_trigger: bool,
    rx1_serial: Optional[str],
    rx2_serial: Optional[str],
    tx_serial: Optional[str],
    rx1_script: Optional[Path] = None,
    rx2_script: Optional[Path] = None,
) -> int:
    '''
    One-shot capture:
      1) start RX1/RX2 python capture scripts
      2) wait for both READY
      3) run TX pulse
      4) wait for RX captures to finish (terminate if needed)

    Returns: 0 if TX rc==0 else TX rc (even if RX had warnings).
    '''
    try:
        require_tool("hackrf_transfer")
        require_tool("python3")
    except RuntimeError as e:
        print(f"[TX][ERROR] {e}", file=sys.stderr)
        return 1

    base_dir = paths.rx1_iq.parent
    base_dir.mkdir(parents=True, exist_ok=True)

    # Locate scripts (default to wrappers in Local/ root)
    local_dir = Path(__file__).resolve().parents[1]  # .../Local
    rx1_py = rx1_script or (local_dir / "rx_1_local.py")
    rx2_py = rx2_script or (local_dir / "rx_2_local.py")

    rx1 = RxProc(
        name="rx1",
        rx_py=rx1_py,
        outfile=paths.rx1_iq,
        log_path=paths.rx1_log,
        serial=rx1_serial,
        lna=rx1_lna if rx1_lna is not None else lna,
        vga=rx1_vga if rx1_vga is not None else vga,
    )
    rx2 = RxProc(
        name="rx2",
        rx_py=rx2_py,
        outfile=paths.rx2_iq,
        log_path=paths.rx2_log,
        serial=rx2_serial,
        lna=rx2_lna if rx2_lna is not None else lna,
        vga=rx2_vga if rx2_vga is not None else vga,
    )

    # ---- Start RX processes and wait for READY ----
    procs: List[Tuple[RxProc, subprocess.Popen]] = []
    ready_events: List[Tuple[RxProc, Event]] = []

    for rx in (rx1, rx2):
        proc, ev, _ = start_local_rx(
            rx=rx,
            freq=freq,
            sr=sr,
            nsamples=nsamples,
            hw_trigger=hw_trigger,
            ready_timeout_s=rx_ready_timeout,
        )
        procs.append((rx, proc))
        ready_events.append((rx, ev))

    print("[TX] Waiting for RX READY from both receivers...")
    t0 = time.monotonic()
    while True:
        if all(ev.is_set() for _, ev in ready_events):
            break

        # If any RX died early, bail with logs
        for rx, proc in procs:
            rc = proc.poll()
            if rc is not None and not any(r.name == rx.name and ev.is_set() for r, ev in ready_events):
                print(f"[TX][ERROR] {rx.name} exited before READY (rc={rc}). Check {rx.log_path}",
                      file=sys.stderr)
                return 2

        if time.monotonic() - t0 > tx_wait_timeout:
            not_ready = [rx.name for rx, ev in ready_events if not ev.is_set()]
            print(f"[TX][ERROR] Timeout waiting for READY from: {', '.join(not_ready)}", file=sys.stderr)
            print("[TX] Check rx1.log / rx2.log for what happened.", file=sys.stderr)
            return 3

        time.sleep(0.01)

    # ---- Trigger TX immediately after both are READY ----
    print("[TX] Both RX READY. Triggering TX now...")
    tx_rc = run_local_tx(
        pulse_iq=pulse,
        freq=freq,
        sr=sr,
        amp=amp,
        rf_amp=rf_amp,
        antenna_power=antenna_power,
        tx_serial=tx_serial,
        tx_log=paths.tx_log,
    )
    if tx_rc != 0:
        print(f"[TX][ERROR] TX hackrf_transfer exited with {tx_rc}", file=sys.stderr)

    # ---- Wait for captures to complete ----
    capture_secs = nsamples / sr
    wait_budget = capture_secs + safety_margin
    print(f"[TX] Waiting ~{wait_budget:.6f}s for RX captures to finish...")

    deadline = time.monotonic() + wait_budget + 2.0  # small extra grace
    for rx, proc in procs:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            rc = proc.wait(timeout=remaining)
            if rc != 0:
                print(f"[TX][WARN] {rx.name} exited with code {rc} (see {rx.log_path})", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"[TX][WARN] {rx.name} still running after wait; terminating.", file=sys.stderr)
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()

    print("[TX] All done. Files saved:")
    print(f"  {paths.rx1_iq}")
    print(f"  {paths.rx2_iq}")
    print(f"  {paths.rx1_log}")
    print(f"  {paths.rx2_log}")
    if paths.tx_log:
        print(f"  {paths.tx_log}")
    return 0 if tx_rc == 0 else tx_rc

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Local (single-machine) TX controller: waits for two local RX READY, transmits, saves captures."
    )
    ap.add_argument("--freq", type=int, default=520_000_000)
    ap.add_argument("--sr", type=int, default=20_000_000)
    ap.add_argument("--nsamples", type=int, default=7_000)

    ap.add_argument("--lna", type=int, default=8)
    ap.add_argument("--vga", type=int, default=8)
    ap.add_argument("--rx1-lna", type=int, default=None, help="Override RX1 LNA gain (else uses --lna)")
    ap.add_argument("--rx1-vga", type=int, default=None, help="Override RX1 VGA gain (else uses --vga)")
    ap.add_argument("--rx2-lna", type=int, default=None, help="Override RX2 LNA gain (else uses --lna)")
    ap.add_argument("--rx2-vga", type=int, default=None, help="Override RX2 VGA gain (else uses --vga)")

    ap.add_argument("--amp", type=int, default=45)

    ap.add_argument("--rf-amp", dest="rf_amp", action="store_true",
                    help="Enable HackRF RF amp (adds -a 1). Default: enabled")
    ap.add_argument("--no-rf-amp", dest="rf_amp", action="store_false",
                    help="Disable HackRF RF amp (adds -a 0)")
    ap.set_defaults(rf_amp=True)

    ap.add_argument("--antenna-power", dest="antenna_power", action="store_true",
                    help="Enable antenna port power / bias-tee (adds -p 1). Default: disabled")
    ap.add_argument("--no-antenna-power", dest="antenna_power", action="store_false",
                    help="Disable antenna port power / bias-tee (adds -p 0)")
    ap.set_defaults(antenna_power=False)

    ap.add_argument("--pulse", default="/opt/TVWS/Codebase/Collection/pilot.iq")
    ap.add_argument("--save-dir", default=str(Path.cwd()))
    ap.add_argument("--prefix", default=None,
                    help="Optional prefix for output files (created inside --save-dir). "
                         "If omitted, uses a UTC timestamp.")
    ap.add_argument("--safety-margin", type=float, default=1.0)

    ap.add_argument("--rx-ready-timeout", type=float, default=0.5,
                    help="Seconds RX waits before emitting READY even if hackrf is silent (default 0.5)")
    ap.add_argument("--tx-wait-timeout", type=float, default=10.0,
                    help="Max seconds TX waits for BOTH RX READY before transmitting (default 10)")
    ap.add_argument("--no-hw-trigger", action="store_true")

    ap.add_argument("--rx1-serial", default=None, help="Serial for RX1 HackRF (passed to hackrf_transfer -d)")
    ap.add_argument("--rx2-serial", default=None, help="Serial for RX2 HackRF (passed to hackrf_transfer -d)")
    ap.add_argument("--tx-serial", default=None, help="Serial for TX HackRF (passed to hackrf_transfer -d)")

    ap.add_argument("--list-devices", action="store_true",
                    help="Print hackrf_info output (connected devices / serials) and exit.")
    ap.add_argument("--tx-log", default=None, help="Optional path to save TX output log.")
    return ap

def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)

    if args.list_devices:
        return list_hackrf_devices()

    save_dir = Path(args.save_dir).expanduser().resolve()
    save_dir.mkdir(parents=True, exist_ok=True)

    prefix = args.prefix or utc_timestamp_for_filename()

    paths = CapturePaths(
        rx1_iq=save_dir / f"{prefix}_capture_1.iq",
        rx2_iq=save_dir / f"{prefix}_capture_2.iq",
        rx1_log=save_dir / "rx1.log",
        rx2_log=save_dir / "rx2.log",
        tx_log=(Path(args.tx_log).expanduser().resolve() if args.tx_log else None),
    )

    hw_trigger = not args.no_hw_trigger

    return run_capture(
        paths=paths,
        freq=args.freq,
        sr=args.sr,
        nsamples=args.nsamples,
        lna=args.lna,
        vga=args.vga,
        rx1_lna=args.rx1_lna,
        rx1_vga=args.rx1_vga,
        rx2_lna=args.rx2_lna,
        rx2_vga=args.rx2_vga,
        amp=args.amp,
        rf_amp=args.rf_amp,
        antenna_power=args.antenna_power,
        pulse=Path(args.pulse).expanduser().resolve(),
        safety_margin=args.safety_margin,
        rx_ready_timeout=args.rx_ready_timeout,
        tx_wait_timeout=args.tx_wait_timeout,
        hw_trigger=hw_trigger,
        rx1_serial=args.rx1_serial,
        rx2_serial=args.rx2_serial,
        tx_serial=args.tx_serial,
    )
