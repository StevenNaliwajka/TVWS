from __future__ import annotations
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional
from Codebase.Collection.Local.util.timeutil import utc_stamp

def compile_ready_patterns(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]

def run_capture_with_ready_handshake(
    outfile: str,
    freq_hz: int,
    sample_rate_hz: int,
    nsamples: int,
    lna: int,
    vga: int,
    hw_trigger: bool,
    ready_timeout_s: float,
    ready_patterns: List[re.Pattern],
    device_serial: Optional[str] = None,
) -> int:
    '''
    Launch hackrf_transfer and emit a single 'READY' line once we believe it's armed.

    - If --hw-trigger is used, hackrf_transfer will wait for a hardware trigger (-H).
    - We try to detect readiness by watching hackrf_transfer output for common trigger-wait phrases.
    - If hackrf_transfer is silent, we still emit READY after ready_timeout_s so TX can proceed.
    - If multiple HackRFs are connected, pass --serial to target a specific unit (maps to hackrf_transfer -d).
    '''

    cmd = [
        "hackrf_transfer",
        "-r", outfile,
        "-n", str(nsamples),
        "-f", str(freq_hz),
        "-s", str(sample_rate_hz),
        "-l", str(lna),
        "-g", str(vga),
    ]

    if device_serial:
        cmd += ["-d", device_serial]

    if hw_trigger:
        cmd.append("-H")

    dev_msg = f" (serial={device_serial})" if device_serial else ""
    print(f"[{utc_stamp()}] START{dev_msg}: {' '.join(cmd)}", flush=True)

    try:
        # text=True, line-buffered helps as long as hackrf outputs newlines
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print("[ERROR] hackrf_transfer not found in PATH.", file=sys.stderr, flush=True)
        return 127

    ready_sent = False
    start_t = time.monotonic()

    try:
        while True:
            line = p.stdout.readline() if p.stdout is not None else ""
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()

                if (not ready_sent) and any(r.search(line) for r in ready_patterns):
                    print("READY", flush=True)
                    ready_sent = True

            rc = p.poll()
            if rc is not None:
                if not ready_sent:
                    print("[RX][WARN] hackrf_transfer exited before READY detection.", flush=True)
                return rc

            if (not ready_sent) and (time.monotonic() - start_t >= ready_timeout_s):
                print("READY", flush=True)
                ready_sent = True

    finally:
        try:
            if p.stdout:
                p.stdout.close()
        except Exception:
            pass

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="RX capture script for HackRF with READY handshake for TX.")
    ap.add_argument("--outfile", default="capture.iq", help="Output IQ filename/path (default: capture.iq)")
    ap.add_argument("--freq", type=int, required=True, help="Center frequency (Hz)")
    ap.add_argument("--sr", type=int, required=True, help="Sample rate (Hz)")
    ap.add_argument("--nsamples", type=int, required=True, help="Number of samples")
    ap.add_argument("--lna", type=int, default=16, help="LNA gain (hackrf_transfer -l). Default 16")
    ap.add_argument("--vga", type=int, default=16, help="VGA gain (hackrf_transfer -g). Default 16")
    ap.add_argument("--hw-trigger", action="store_true", help="Wait for hardware trigger (-H)")

    ap.add_argument("--serial", default=None,
                    help="HackRF serial to use (passed to hackrf_transfer -d).")

    ap.add_argument("--ready-timeout", type=float, default=0.5,
                    help="Seconds before emitting READY even if hackrf is silent (default 0.5)")

    ap.add_argument("--ready-pattern", action="append", default=[
        r"wait.*trigger",
        r"waiting.*trigger",
        r"trigger.*armed",
        r"armed",
    ], help="Regex to detect 'armed' state from hackrf output (repeatable).")

    return ap

def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)

    ready_regexes = compile_ready_patterns(args.ready_pattern)

    rc = run_capture_with_ready_handshake(
        outfile=args.outfile,
        freq_hz=args.freq,
        sample_rate_hz=args.sr,
        nsamples=args.nsamples,
        lna=args.lna,
        vga=args.vga,
        hw_trigger=args.hw_trigger,
        ready_timeout_s=args.ready_timeout,
        ready_patterns=ready_regexes,
        device_serial=args.serial,
    )

    if rc == 0:
        print(f"[{utc_stamp()}] DONE: capture saved to {args.outfile}", flush=True)
    else:
        print(f"[{utc_stamp()}] ERROR: hackrf_transfer exited with code {rc}", flush=True)

    return rc
