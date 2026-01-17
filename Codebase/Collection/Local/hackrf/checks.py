from __future__ import annotations

import shutil
import subprocess


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
