#!/usr/bin/env python3
"""
Create (or reuse) the project's .venv and install dependencies.

This script is designed to be run from:
  <project-root>/Codebase/Setup/create_venv.py

Default layout:
  <project-root>/Codebase/Setup/requirements.json
  <project-root>/.venv/

Key features:
- Correct project-root detection (2 levels above Codebase/Setup)
- Installs *pip* packages into the venv
- Optionally installs *apt* packages on Debian/Raspberry Pi OS (e.g., sshpass)
- Supports a richer requirements.json schema while remaining backward-compatible

requirements.json formats supported:
1) Legacy (pip-only):
   ["numpy", "pandas==2.2.0"]

2) Legacy dict (pip-only):
   {"packages": ["numpy", "pandas==2.2.0"]}

3) Recommended (pip + apt):
   {
     "pip": ["numpy", "pandas==2.2.0"],
     "apt": ["sshpass"]
   }

Notes:
- "sshpass" is a *system* package (apt), not a pip package. If it appears in
  pip lists, we auto-move it to apt (with a warning) on Linux.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any, Iterable


# -----------------------------
# Platform helpers
# -----------------------------

def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def venv_python_path(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if is_windows() else "bin/python")


# -----------------------------
# Process helpers
# -----------------------------

def run(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env, cwd=str(cwd) if cwd else None)


def which(exe: str) -> str | None:
    return shutil.which(exe)


def is_root() -> bool:
    if is_windows():
        return False
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except Exception:
        return False


# -----------------------------
# Requirements parsing
# -----------------------------

# Packages that are commonly mistaken as pip packages but are system packages
# for Debian/RPi OS (your current requirements.json includes sshpass).
KNOWN_APT_ONLY = {"sshpass"}


def _ensure_list(value: Any, key_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key_name} must be a list.")
    out: list[str] = []
    for item in value:
        s = str(item).strip()
        if s:
            out.append(s)
    return out


def load_requirements(req_json: Path) -> tuple[list[str], list[str]]:
    """
    Returns (pip_packages, apt_packages) from requirements.json.
    Backward-compatible with older formats.
    """
    with req_json.open("r", encoding="utf-8") as f:
        data = json.load(f)

    pip_pkgs: list[str] = []
    apt_pkgs: list[str] = []

    if isinstance(data, list):
        # Legacy list => pip
        pip_pkgs = _ensure_list(data, "requirements.json (list)")
    elif isinstance(data, dict):
        # Newer: prefer explicit keys
        if "pip" in data or "apt" in data:
            pip_pkgs = _ensure_list(data.get("pip"), "pip")
            apt_pkgs = _ensure_list(data.get("apt"), "apt")
        else:
            # Legacy dict: {"packages": [...]}
            pip_pkgs = _ensure_list(data.get("packages"), "packages")
    else:
        raise ValueError("requirements.json must be a list or a dict.")

    # Auto-move known apt-only packages out of pip list on Linux
    if is_linux() and pip_pkgs:
        moved: list[str] = []
        kept: list[str] = []
        for p in pip_pkgs:
            name = p.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip().lower()
            if name in KNOWN_APT_ONLY:
                moved.append(p)
                # add base name to apt list if not already present
                if name not in {a.lower() for a in apt_pkgs}:
                    apt_pkgs.append(name)
            else:
                kept.append(p)
        if moved:
            print("[WARN] These entries are not pip packages; treating them as apt packages instead:")
            for m in moved:
                print(f"  - {m}")
            pip_pkgs = kept

    return pip_pkgs, apt_pkgs


# -----------------------------
# apt installation (Linux)
# -----------------------------

def install_apt_packages(apt_pkgs: list[str], *, assume_yes: bool = True) -> None:
    if not apt_pkgs:
        return

    if not is_linux():
        print("[INFO] apt packages requested but OS is not Linux; skipping apt install.")
        return

    if which("apt-get") is None:
        print("[WARN] apt-get not found; cannot install system packages. Requested:", ", ".join(apt_pkgs))
        return

    # Build command (use sudo if not root and sudo exists)
    prefix: list[str] = []
    if not is_root():
        if which("sudo") is None:
            raise RuntimeError(
                "Need root privileges to install apt packages, but 'sudo' is not available. "
                "Re-run as root (sudo) or install packages manually."
            )
        prefix = ["sudo"]

    yes_flag = ["-y"] if assume_yes else []
    print("[INFO] Installing apt packages:")
    for p in apt_pkgs:
        print(f"  {p}")

    run(prefix + ["apt-get", "update"])
    run(prefix + ["apt-get", "install", *yes_flag, *apt_pkgs])


# -----------------------------
# venv + pip installation
# -----------------------------

def create_or_reuse_venv(venv_dir: Path, *, recreate: bool = False) -> None:
    if recreate and venv_dir.exists():
        print(f"[INFO] Recreating venv: removing {venv_dir}")
        shutil.rmtree(venv_dir, ignore_errors=True)

    if not venv_dir.is_dir():
        print("[INFO] Creating virtual environment...")
        venv.EnvBuilder(with_pip=True).create(str(venv_dir))
    else:
        print("[INFO] Virtual environment already exists; reusing it.")


def upgrade_pip_tooling(vpy: Path) -> None:
    print("[INFO] Upgrading pip/setuptools/wheel...")
    run([str(vpy), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])


def install_pip_packages(vpy: Path, pip_pkgs: list[str]) -> None:
    if not pip_pkgs:
        print("[INFO] No pip packages requested; skipping pip install.")
        return

    print("[INFO] Installing pip packages:")
    for p in pip_pkgs:
        print(f"  {p}")
    run([str(vpy), "-m", "pip", "install", *pip_pkgs])


# -----------------------------
# Root detection for project
# -----------------------------

def detect_project_root(script_dir: Path) -> Path:
    """
    If script_dir = <root>/Codebase/Setup, then project_root = <root>.
    That is two levels up from Setup.
    """
    # script_dir parents:
    # 0: Setup
    # 1: Codebase
    # 2: <project-root>
    if len(script_dir.parents) < 3:
        return script_dir.parents[0]
    return script_dir.parents[2]


# -----------------------------
# CLI
# -----------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create/reuse .venv and install dependencies.")
    p.add_argument("--project-root", type=Path, default=None, help="Override project root directory.")
    p.add_argument("--venv-dir", type=Path, default=None, help="Override venv dir (default: <root>/.venv).")
    p.add_argument("--requirements", type=Path, default=None, help="Override requirements.json path.")
    p.add_argument("--recreate", action="store_true", help="Delete and recreate the venv.")
    p.add_argument("--no-install", action="store_true", help="Create/reuse venv but do not install anything.")
    p.add_argument("--no-apt", action="store_true", help="Skip apt installs even if requested.")
    p.add_argument("--no-pip", action="store_true", help="Skip pip installs even if requested.")
    p.add_argument("--no-upgrade-pip", action="store_true", help="Skip upgrading pip/setuptools/wheel.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    script_dir = Path(__file__).resolve().parent

    project_root = detect_project_root(script_dir)
    args = parse_args(argv)

    if args.project_root is not None:
        project_root = args.project_root.resolve()

    venv_dir = (args.venv_dir.resolve() if args.venv_dir else (project_root / ".venv"))
    req_json = (args.requirements.resolve() if args.requirements else (script_dir / "requirements.json"))

    print(f"Script dir     : {script_dir}")
    print(f"Project root   : {project_root}")
    print(f"Venv dir       : {venv_dir}")
    print(f"Requirements   : {req_json}")
    print(f"Platform       : {platform.platform()}")
    print()

    if not req_json.is_file():
        print(f"[ERROR] requirements.json not found at: {req_json}", file=sys.stderr)
        return 1

    try:
        pip_pkgs, apt_pkgs = load_requirements(req_json)
    except Exception as e:
        print(f"[ERROR] Failed to parse requirements.json: {e}", file=sys.stderr)
        return 1

    # Create/reuse venv
    try:
        create_or_reuse_venv(venv_dir, recreate=bool(args.recreate))
    except Exception as e:
        print(f"[ERROR] Failed to create/reuse venv: {e}", file=sys.stderr)
        return 1

    vpy = venv_python_path(venv_dir)
    if not vpy.is_file():
        print(f"[ERROR] venv python not found at: {vpy}", file=sys.stderr)
        return 1

    if args.no_install:
        print("[INFO] --no-install specified; done.")
        print_activation_hint(venv_dir)
        return 0

    # Install apt packages first (so pip packages depending on system libs have a chance)
    if (not args.no_apt) and apt_pkgs:
        try:
            install_apt_packages(apt_pkgs, assume_yes=True)
        except Exception as e:
            print(f"[ERROR] apt install failed: {e}", file=sys.stderr)
            return 1
    elif apt_pkgs and args.no_apt:
        print("[INFO] --no-apt specified; skipping apt packages:", ", ".join(apt_pkgs))

    # Upgrade pip tooling
    if not args.no_upgrade_pip:
        try:
            upgrade_pip_tooling(vpy)
        except Exception as e:
            print(f"[ERROR] pip tooling upgrade failed: {e}", file=sys.stderr)
            return 1

    # Install pip packages
    if (not args.no_pip) and pip_pkgs:
        try:
            install_pip_packages(vpy, pip_pkgs)
        except subprocess.CalledProcessError as e:
            print("[ERROR] pip install failed.", file=sys.stderr)
            print("Tip: If this failed due to a system package (like sshpass), move it under 'apt' in requirements.json.", file=sys.stderr)
            return int(e.returncode or 1)
        except Exception as e:
            print(f"[ERROR] pip install failed: {e}", file=sys.stderr)
            return 1
    elif pip_pkgs and args.no_pip:
        print("[INFO] --no-pip specified; skipping pip packages.")

    print()
    print("[INFO] Done.")
    print_activation_hint(venv_dir)
    print()
    print("[INFO] Venv python:")
    print(f"  {vpy}")
    return 0


def print_activation_hint(venv_dir: Path) -> None:
    print("To activate later:")
    if is_windows():
        print(f'  {venv_dir}\\Scripts\\activate')
    else:
        print(f'  source "{venv_dir}/bin/activate"')


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
