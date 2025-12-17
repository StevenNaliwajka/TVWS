#!/usr/bin/env python3
"""
Create (or reuse) key project folders.

Expected layout:
  Codebase/Setup/make_folders.py
  <project-root>/Data
  <project-root>/Config
"""

from __future__ import annotations

from pathlib import Path


def create_dir_if_missing(dir_path: Path, name: str) -> None:
    if not dir_path.is_dir():
        print(f"Creating {name} folder at: {dir_path}")
        dir_path.mkdir(parents=True, exist_ok=True)
    else:
        print(f"{name} folder already exists at: {dir_path}, reusing it.")


def main() -> int:
    # Figure out PROJECT_ROOT based on this script's location:
    # .../NeuralNetworksProject/Codebase/Setup/make_folders.py
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[1]  # Codebase/Setup -> project root

    # DIR locations
    data_dir = project_root / "Data"
    config_dir = project_root / "Config"

    create_dir_if_missing(data_dir, "Data")
    create_dir_if_missing(config_dir, "Config")
    create_dir_if_missing(config_dir, "Logs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
