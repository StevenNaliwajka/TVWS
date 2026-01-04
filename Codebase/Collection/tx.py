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


@dataclass(frozen=True)
class RxHost:
    name: str
    user: str
    host: str
    remote_rx_py: str
    remote_outfile: str
    local_log: str
    lna_override: Optional[int] = None
    vga_override: Optional[int] = None


def utc_timestamp_for_filename() -> str:
    dt = datetime.utcnow()
    return f"{dt:%Y-%m-%dT%H-%M-%S}_{dt.microsecond // 100:04d}"


def require_tool(tool: str) -> None:
    from shutil import which
    if which(tool) is None:
        raise RuntimeError(f"Required tool not found in PATH: {tool}")


def _tee_and_detect_ready(
    rx: RxHost,
    proc: subprocess.Popen,
    log_path: str,
    ready_event: Event,
) -> None:
    """
    Reads stdout from proc, writes it to a log file, and sets ready_event when it sees 'READY'.
    """
    with open(log_path, "wb") as lf:
        while True:
            chunk = proc.stdout.readline() if proc.stdout is not None else b""
            if chunk:
                lf.write(chunk)
                lf.flush()

                # Detect READY line (exact match trimmed)
                try:
                    line = chunk.decode("utf-8", errors="replace").strip()
                except Exception:
                    line = ""

                if line == "READY":
                    ready_event.set()

            if proc.poll() is not None:
                # drain remaining buffered output quickly
                if proc.stdout is not None:
                    rest = proc.stdout.read()
                    if rest:
                        lf.write(rest)
                        lf.flush()
                return


def start_remote_rx_with_handshake(
    password: str,
    rx: RxHost,
    freq: int,
    sr: int,
    nsamples: int,
    lna: int,
    vga: int,
    hw_trigger: bool,
    ready_timeout_s: float,
) -> Tuple[subprocess.Popen, Event, Thread]:
    """
    Launch rx.py on the remote host via SSH and return:
      (process, ready_event, reader_thread)
    """
    remote_cmd_parts = [
        "python3", "-u",  # -u is important: unbuffered stdout so READY arrives immediately
        rx.remote_rx_py,
        "--outfile", rx.remote_outfile,
        "--freq", str(freq),
        "--sr", str(sr),
        "--nsamples", str(nsamples),
        "--lna", str(lna),
        "--vga", str(vga),
        "--ready-timeout", str(ready_timeout_s),
    ]
    if hw_trigger:
        remote_cmd_parts.append("--hw-trigger")

    remote_cmd = " ".join(remote_cmd_parts)

    ssh_cmd = [
        "sshpass", "-p", password,
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        f"{rx.user}@{rx.host}",
        remote_cmd,
    ]

    print(f"[TX] Starting {rx.name}: {rx.user}@{rx.host}")
    print(f"[TX] Remote cmd: {remote_cmd}")
    print(f"[TX] Logging to: {rx.local_log}")

    proc = subprocess.Popen(
        ssh_cmd,
        stdout=subprocess.PIPE,        # <-- IMPORTANT: we read it to detect READY
        stderr=subprocess.STDOUT,
        bufsize=0,
    )

    ready_event = Event()
    t = Thread(target=_tee_and_detect_ready, args=(rx, proc, rx.local_log, ready_event), daemon=True)
    t.start()

    return proc, ready_event, t


def run_local_tx(pulse_iq: str, freq: int, sr: int, amp: int) -> int:
    cmd = ["hackrf_transfer", "-t", pulse_iq, "-f", str(freq), "-s", str(sr), "-x", str(amp)]
    print(f"[TX] Transmitting: {' '.join(cmd)}")
    try:
        p = subprocess.run(cmd, check=False)
        return p.returncode
    except FileNotFoundError:
        print("[TX][ERROR] hackrf_transfer not found in PATH.", file=sys.stderr)
        return 127


def scp_from_remote(password: str, user: str, host: str, remote_path: str, local_dir: Path) -> int:
    cmd = [
        "sshpass", "-p", password,
        "scp",
        "-o", "StrictHostKeyChecking=no",
        f"{user}@{host}:{remote_path}",
        str(local_dir),
    ]
    print(f"[TX] Copying {user}@{host}:{remote_path} -> {local_dir}")
    p = subprocess.run(cmd, check=False)
    return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="TX controller: waits for RX READY, transmits, then SCPs captures back.")
    ap.add_argument("--freq", type=int, default=520_000_000)
    ap.add_argument("--sr", type=int, default=20_000_000)
    ap.add_argument("--nsamples", type=int, default=7_000)
    ap.add_argument("--lna", type=int, default=32)
    ap.add_argument("--vga", type=int, default=32)
    ap.add_argument("--rx1-lna", type=int, default=None, help="Override RX1 LNA gain (else uses --lna)")
    ap.add_argument("--rx1-vga", type=int, default=None, help="Override RX1 VGA gain (else uses --vga)")
    ap.add_argument("--rx2-lna", type=int, default=None, help="Override RX2 LNA gain (else uses --lna)")
    ap.add_argument("--rx2-vga", type=int, default=None, help="Override RX2 VGA gain (else uses --vga)")
    ap.add_argument("--amp", type=int, default=45)
    ap.add_argument("--pulse", default="/opt/TVWS/Codebase/Collection/pilot.iq")
    ap.add_argument("--pass", dest="password", default="Kennesaw123")
    ap.add_argument("--save-dir", default=str(Path.home() / "sdr"))
    ap.add_argument("--safety-margin", type=float, default=1.0)

    # New:
    ap.add_argument("--rx-ready-timeout", type=float, default=0.5,
                    help="Seconds RX waits before emitting READY even if hackrf is silent (default 0.5)")
    ap.add_argument("--tx-wait-timeout", type=float, default=10.0,
                    help="Max seconds TX waits for BOTH RX READY before transmitting (default 10)")
    ap.add_argument("--no-hw-trigger", action="store_true")

    args = ap.parse_args()

    try:
        require_tool("sshpass")
        require_tool("ssh")
        require_tool("scp")
        require_tool("hackrf_transfer")
    except RuntimeError as e:
        print(f"[TX][ERROR] {e}", file=sys.stderr)
        return 1

    save_dir = Path(args.save_dir).expanduser()
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = utc_timestamp_for_filename()
    print(f"[TX] Timestamp: {timestamp}")

    rx1 = RxHost(
        name="rx1",
        user="pi1",
        host="100.101.107.104",
        remote_rx_py="/opt/TVWS/Codebase/Collection/rx_1.py",
        remote_outfile="/home/pi1/capture_1.iq",
        local_log="rx1.log",
        lna_override=args.rx1_lna,
        vga_override=args.rx1_vga,
    )
    rx2 = RxHost(
        name="rx2",
        user="pi2",
        host="100.85.78.54",
        remote_rx_py="/opt/TVWS/Codebase/Collection/rx_2.py",
        remote_outfile="/home/pi2/capture_2.iq",
        local_log="rx2.log",
        lna_override=args.rx2_lna,
        vga_override=args.rx2_vga,
    )
    rx_hosts = [rx1, rx2]

    hw_trigger = not args.no_hw_trigger

    # ---- Start RX processes and wait for READY ----
    procs = []
    ready_events = []

    for rx in rx_hosts:
        lna = rx.lna_override if rx.lna_override is not None else args.lna
        vga = rx.vga_override if rx.vga_override is not None else args.vga

        proc, ev, th = start_remote_rx_with_handshake(
            password=args.password,
            rx=rx,
            freq=args.freq,
            sr=args.sr,
            nsamples=args.nsamples,
            lna=lna,
            vga=vga,
            hw_trigger=hw_trigger,
            ready_timeout_s=args.rx_ready_timeout,
        )
        procs.append((rx, proc))
        ready_events.append((rx, ev))

    print("[TX] Waiting for RX READY from both receivers...")
    t0 = time.monotonic()
    while True:
        all_ready = all(ev.is_set() for _, ev in ready_events)
        if all_ready:
            break

        # If any RX died early, bail with logs
        for rx, proc in procs:
            rc = proc.poll()
            if rc is not None and not any(r.name == rx.name and ev.is_set() for r, ev in ready_events):
                print(f"[TX][ERROR] {rx.name} exited before READY (rc={rc}). Check {rx.local_log}", file=sys.stderr)
                return 2

        if time.monotonic() - t0 > args.tx_wait_timeout:
            not_ready = [rx.name for rx, ev in ready_events if not ev.is_set()]
            print(f"[TX][ERROR] Timeout waiting for READY from: {', '.join(not_ready)}", file=sys.stderr)
            print("[TX] Check rx1.log / rx2.log for what happened.", file=sys.stderr)
            return 3

        time.sleep(0.01)  # very short; just prevents a tight CPU spin

    # ---- Trigger TX immediately after both are READY ----
    print(f"[TX] [{timestamp}] Both RX READY. Triggering TX now...")
    tx_rc = run_local_tx(args.pulse, args.freq, args.sr, args.amp)
    if tx_rc != 0:
        print(f"[TX][ERROR] TX hackrf_transfer exited with {tx_rc}", file=sys.stderr)

    # ---- Wait for captures to complete ----
    capture_secs = args.nsamples / args.sr
    sleep_time = capture_secs + args.safety_margin
    print(f"[TX] Waiting {sleep_time:.6f}s for remote captures to finish...")
    time.sleep(sleep_time)

    # ---- Copy captures back ----
    local_rx1_name = save_dir / f"{timestamp}_capture_1.iq"
    local_rx2_name = save_dir / f"{timestamp}_capture_2.iq"

    rc1 = scp_from_remote(args.password, rx1.user, rx1.host, rx1.remote_outfile, save_dir)
    rc2 = scp_from_remote(args.password, rx2.user, rx2.host, rx2.remote_outfile, save_dir)

    if rc1 == 0:
        src = save_dir / Path(rx1.remote_outfile).name
        if src.exists():
            src.replace(local_rx1_name)
    else:
        print("[TX][WARN] Failed to copy rx1 capture.", file=sys.stderr)

    if rc2 == 0:
        src = save_dir / Path(rx2.remote_outfile).name
        if src.exists():
            src.replace(local_rx2_name)
    else:
        print("[TX][WARN] Failed to copy rx2 capture.", file=sys.stderr)

    print("[TX] All done. Files saved:")
    print(f"  {local_rx1_name}")
    print(f"  {local_rx2_name}")
    return 0 if tx_rc == 0 else tx_rc


if __name__ == "__main__":
    raise SystemExit(main())
