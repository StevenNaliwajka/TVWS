#!/usr/bin/env python3
"""
Codebase/Setup/get_project_reqs.py

Runs pigar to generate requirements.txt from imports:

  pigar gen -f Codebase/Setup/requirements.txt ./Codebase

Then converts requirements.txt -> requirements.json in the form:

{
  "packages": [
    "matplotlib>=3.8.0",
    "findpeaks"
  ]
}

Finally removes requirements.txt after conversion.

Run:
  python Codebase/Setup/get_project_reqs.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _read_requirements_txt(req_txt: Path) -> list[str]:
    """
    Read pip-style requirements.txt and return normalized requirement strings.
    - Strips comments and blank lines.
    - Keeps version specifiers if present.
    - Deduplicates while preserving order.
    """
    if not req_txt.exists():
        return []

    out: list[str] = []
    seen: set[str] = set()

    for raw_line in req_txt.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()

        # Skip blanks / pure comments
        if not line or line.startswith("#"):
            continue

        # Remove trailing inline comments: "pkg>=1.0  # comment"
        if " #" in line:
            line = line.split(" #", 1)[0].strip()

        # Skip pip directives / uncommon entries (keep it simple + safe)
        # If you want these supported, tell me.
        if line.startswith(("-r ", "--requirement", "--index-url", "--extra-index-url", "--find-links")):
            continue
        if line.startswith(("-e ", "--editable")):
            # Drop editable installs from JSON list (typically local paths)
            continue
        if "://" in line:
            # Likely a URL requirement; skip for JSON list
            continue

        key = line.lower()
        if key not in seen:
            seen.add(key)
            out.append(line)

    return out


def main() -> int:
    script_dir = Path(__file__).resolve().parent          # .../Codebase/Setup
    project_root = script_dir.parent.parent               # .../<PROJECT_ROOT>

    codebase_dir = project_root / "Codebase"
    out_req_txt = script_dir / "requirements.txt"         # Codebase/Setup/requirements.txt
    out_req_json = script_dir / "requirements.json"       # Codebase/Setup/requirements.json

    if not codebase_dir.is_dir():
        raise FileNotFoundError(f"Codebase folder not found at: {codebase_dir}")

    pigar_exe = shutil.which("pigar")
    if not pigar_exe:
        raise RuntimeError(
            "pigar not found on PATH.\n"
            "Install it with:\n"
            "  python -m pip install pigar\n"
            "If you're using a venv, activate it first."
        )

    # pigar usage:
    #   pigar gen -f <file> <dir>
    cmd = [pigar_exe, "gen", "-f", str(out_req_txt), str(codebase_dir)]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(project_root))
    print(f"Done. Wrote: {out_req_txt}")

    # ---- Convert requirements.txt -> requirements.json ----
    packages = _read_requirements_txt(out_req_txt)

    payload = {"packages": packages}
    out_req_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Converted -> {out_req_json} ({len(packages)} package(s))")

    # ---- Remove requirements.txt after conversion ----
    try:
        out_req_txt.unlink(missing_ok=True)
        print(f"Removed: {out_req_txt}")
    except Exception as e:
        print(f"Warning: could not remove {out_req_txt}: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
