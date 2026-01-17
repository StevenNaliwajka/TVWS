from __future__ import annotations

import subprocess
import time
from pathlib import Path


def _popen_to_files(cmd: list[str], log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    f = log_path.open("w", encoding="utf-8")
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
    deadline = time.time() + timeout_s
    if min_delay_s > 0:
        time.sleep(min_delay_s)

    last_size = -1
    while time.time() < deadline:
        try:
            if log_path.exists():
                size = log_path.stat().st_size
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
