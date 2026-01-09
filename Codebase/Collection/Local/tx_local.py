#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Optional, Tuple


def utc_timestamp_for_filename() -> str:
    dt = datetime.utcnow()
    return f"{dt:%Y-%m-%dT%H-%M-%S}_{dt.microsecond // 100:04d}"


def require_tool(tool: str) -> None:
    from shutil import which
    if which(tool) is None:
        raise RuntimeError(f"Required tool not found in PATH: {tool}")


def run_cmd_capture_text(cmd: list) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return p.returncode, p.stdout or ""
    except FileNotFoundError:
        return 127, f"[ERROR] Tool not found: {cmd[0]}"


def list_hackrf_devices() -> int:
    rc, out = run_cmd_capture_text(["hackrf_info"])
    print(out, end="" if out.endswith("\n") else "\n")
    return rc


@dataclass(frozen=True)
class RxProc:
    name: str
    rx_py: str
    outfile: Path
    log_path: Path
    serial: Optional[str]
    lna: int
    vga: int


def _tee_and_detect_ready(proc: subprocess.Popen, log_path: Path, ready_event: Event) -> None:
    """Reads stdout, writes to log, sets ready_event when it sees an exact 'READY' line."""
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
        rx.rx_py,
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


def run_local_tx(pulse_iq: str, freq: int, sr: int, amp: int, rf_amp: bool,
                 antenna_power: bool, tx_serial: Optional[str]) -> int:
    cmd = [
        "hackrf_transfer",
        "-t", pulse_iq,
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
        p = subprocess.run(cmd, check=False)
        return p.returncode
    except FileNotFoundError:
        print("[TX][ERROR] hackrf_transfer not found in PATH.", file=sys.stderr)
        return 127


def main() -> int:
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
    ap.add_argument("--safety-margin", type=float, default=1.0)

    ap.add_argument("--rx-ready-timeout", type=float, default=0.5,
                    help="Seconds RX waits before emitting READY even if hackrf is silent (default 0.5)")
    ap.add_argument("--tx-wait-timeout", type=float, default=10.0,
                    help="Max seconds TX waits for BOTH RX READY before transmitting (default 10)")
    ap.add_argument("--no-hw-trigger", action="store_true")

    # New: explicit device selection when 3 HackRFs are plugged into one host.
    ap.add_argument("--rx1-serial", default=None, help="Serial for RX1 HackRF (passed to hackrf_transfer -d)")
    ap.add_argument("--rx2-serial", default=None, help="Serial for RX2 HackRF (passed to hackrf_transfer -d)")
    ap.add_argument("--tx-serial", default=None, help="Serial for TX HackRF (passed to hackrf_transfer -d)")

    ap.add_argument("--list-devices", action="store_true",
                    help="Print hackrf_info output (connected devices / serials) and exit.")

    args = ap.parse_args()

    if args.list_devices:
        return list_hackrf_devices()

    try:
        require_tool("hackrf_transfer")
        require_tool("python3")
    except RuntimeError as e:
        print(f"[TX][ERROR] {e}", file=sys.stderr)
        return 1

    save_dir = Path(args.save_dir).expanduser().resolve()
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = utc_timestamp_for_filename()
    print(f"[TX] Timestamp: {timestamp}")
    print(f"[TX] Save dir : {save_dir}")

    rx1_out = save_dir / f"{timestamp}_capture_1.iq"
    rx2_out = save_dir / f"{timestamp}_capture_2.iq"
    rx1_log = save_dir / "rx1.log"
    rx2_log = save_dir / "rx2.log"

    rx1 = RxProc(
        name="rx1",
        rx_py=str(Path(__file__).with_name("rx_1.py")),
        outfile=rx1_out,
        log_path=rx1_log,
        serial=args.rx1_serial,
        lna=args.rx1_lna if args.rx1_lna is not None else args.lna,
        vga=args.rx1_vga if args.rx1_vga is not None else args.vga,
    )
    rx2 = RxProc(
        name="rx2",
        rx_py=str(Path(__file__).with_name("rx_2.py")),
        outfile=rx2_out,
        log_path=rx2_log,
        serial=args.rx2_serial,
        lna=args.rx2_lna if args.rx2_lna is not None else args.lna,
        vga=args.rx2_vga if args.rx2_vga is not None else args.vga,
    )

    hw_trigger = not args.no_hw_trigger

    # ---- Start RX processes and wait for READY ----
    procs = []
    ready_events = []

    for rx in (rx1, rx2):
        proc, ev, _ = start_local_rx(
            rx=rx,
            freq=args.freq,
            sr=args.sr,
            nsamples=args.nsamples,
            hw_trigger=hw_trigger,
            ready_timeout_s=args.rx_ready_timeout,
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

        if time.monotonic() - t0 > args.tx_wait_timeout:
            not_ready = [rx.name for rx, ev in ready_events if not ev.is_set()]
            print(f"[TX][ERROR] Timeout waiting for READY from: {', '.join(not_ready)}", file=sys.stderr)
            print("[TX] Check rx1.log / rx2.log for what happened.", file=sys.stderr)
            return 3

        time.sleep(0.01)

    # ---- Trigger TX immediately after both are READY ----
    print(f"[TX] [{timestamp}] Both RX READY. Triggering TX now...")
    tx_rc = run_local_tx(
        pulse_iq=args.pulse,
        freq=args.freq,
        sr=args.sr,
        amp=args.amp,
        rf_amp=args.rf_amp,
        antenna_power=args.antenna_power,
        tx_serial=args.tx_serial,
    )
    if tx_rc != 0:
        print(f"[TX][ERROR] TX hackrf_transfer exited with {tx_rc}", file=sys.stderr)

    # ---- Wait for captures to complete ----
    capture_secs = args.nsamples / args.sr
    wait_budget = capture_secs + args.safety_margin
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
    print(f"  {rx1_out}")
    print(f"  {rx2_out}")
    print(f"  {rx1_log}")
    print(f"  {rx2_log}")
    return 0 if tx_rc == 0 else tx_rc


if __name__ == "__main__":
    raise SystemExit(main())
