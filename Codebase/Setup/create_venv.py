#!/usr/bin/env python3
"""
Create (or reuse) the project's .venv and install packages listed in requirements.json.

Expected layout:
  Codebase/Setup/create_venv.py
  Codebase/Setup/requirements.json
  <project-root>/.venv
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _venv_python_path(venv_dir: Path) -> Path:
    if _is_windows():
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(cmd: list[str], *, env: dict | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def _load_packages(req_json: Path) -> list[str]:
    with req_json.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Accept either:
    # 1) ["pkg1==1.0", "pkg2>=2.0"]
    # 2) {"packages": ["pkg1==1.0", "pkg2>=2.0"]}
    if isinstance(data, dict):
        pkgs = data.get("packages", [])
    else:
        pkgs = data

    if not isinstance(pkgs, list):
        raise ValueError("requirements.json must be a list or a dict containing a 'packages' list.")

    return [str(p).strip() for p in pkgs if str(p).strip()]


def main() -> int:
    # Location of this script (Codebase/Setup)
    script_dir = Path(__file__).resolve().parent

    # Project root: go up two levels from Codebase/Setup → NeuralNetworksProject
    project_root = script_dir.parents[1]

    venv_dir = project_root / ".venv"
    req_json = script_dir / "requirements.json"

    print(f"Script dir:      {script_dir}")
    print(f"Project root:    {project_root}")
    print(f"Virtualenv dir:  {venv_dir}")
    print(f"Requirements:    {req_json}")
    print()

    if not req_json.is_file():
        print(f"ERROR: requirements.json not found at: {req_json}", file=sys.stderr)
        return 1

    # Create venv if it doesn't exist
    if not venv_dir.is_dir():
        print("Creating virtual environment...")
        venv.EnvBuilder(with_pip=True).create(str(venv_dir))
    else:
        print("Virtual environment already exists, reusing it.")

    vpy = _venv_python_path(venv_dir)
    if not vpy.is_file():
        print(f"ERROR: venv python not found at: {vpy}", file=sys.stderr)
        return 1

    print("Upgrading pip...")
    _run([str(vpy), "-m", "pip", "install", "--upgrade", "pip"])

    print("Parsing requirements.json...")
    try:
        pkgs = _load_packages(req_json)
    except Exception as e:
        print(f"ERROR: failed to parse requirements.json: {e}", file=sys.stderr)
        return 1

    if not pkgs:
        print("No packages found in requirements.json; skipping pip install.")
    else:
        print("Installing packages:")
        for p in pkgs:
            print(f"  {p}")
        _run([str(vpy), "-m", "pip", "install", *pkgs])

    print()
    print("Done! To use the environment later, run:")
    if _is_windows():
        print(f'  {venv_dir}\\Scripts\\activate')
    else:
        print(f'  source "{venv_dir}/bin/activate"')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
