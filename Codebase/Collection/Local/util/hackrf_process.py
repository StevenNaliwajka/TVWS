from __future__ import annotations
import subprocess
import time
from typing import Optional, List

def list_hackrf_transfer_procs() -> str:
    # Returns lines (may be empty) for current hackrf_transfer processes.
    try:
        p = subprocess.run(["pgrep", "-fa", "hackrf_transfer"], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
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
    # True if free within timeout, else False.
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
    # Kill ONLY processes matching the exact serial.
    # Note: this uses pkill -f, so run under sudo if needed.
    try:
        subprocess.run(["pkill", "-f", f"hackrf_transfer.*-d[[:space:]]*{serial}"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    except FileNotFoundError:
        return

def cleanup_hackrf_all(serials: List[Optional[str]]) -> None:
    for s in serials:
        cleanup_hackrf_serial(s)
