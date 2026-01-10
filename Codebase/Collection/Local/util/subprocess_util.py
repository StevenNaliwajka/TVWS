from __future__ import annotations
import subprocess
from shutil import which
from typing import Tuple, List

def require_tool(tool: str) -> None:
    if which(tool) is None:
        raise RuntimeError(f"Required tool not found in PATH: {tool}")

def run_cmd_capture_text(cmd: List[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return p.returncode, p.stdout or ""
    except FileNotFoundError:
        return 127, f"[ERROR] Tool not found: {cmd[0]}"
