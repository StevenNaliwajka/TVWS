# Codebase/Setup/setup_config.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def _project_root() -> Path:
    """
    Infer PROJECT_ROOT from this file location:
      .../PROJECT_ROOT/Codebase/Setup/setup_config.py
    """
    return Path(__file__).resolve().parents[2]


def _metadata_json_path() -> Path:
    """
    Target:
      PROJECT_ROOT/Codebase/Config/metadata.json
    """
    return _project_root() / "Config" / "metadata.json"


def _default_metadata() -> Dict[str, Any]:
    """
    Default values you specified.
    NOTE: JSON needs escaped backslashes for Windows paths.
    """
    return {
      "baseband_hz": 491000000,
      "sync_hz": 493000000,
      "signal_tx_hz": 489000000,
      "sample_rate_hz": 20000000,
      "wired_iq_file_path": "C:\\Users\\steve\\PycharmProjects\\TVWS\\Data\\Wired\\20251119_22-41-36_1763610096_rx1_2ft01616_tx030.iq",
      "selected_iq_path": "C:\\Users\\steve\\PycharmProjects\\TVWS\\Data\\10 Feet\\20251119_23-24-44_1763612684_rx2_10ft14030_tx044.iq",
      "edge_percentage": 0.98,
      "qty_peaks": 4
    }


def write_default_metadata_json(overwrite: bool = False) -> Path:
    """
    Create Codebase/Config/metadata.json with default values.

    - If overwrite=False (default): will NOT overwrite an existing file.
    - If overwrite=True: replaces the file contents.

    Returns the path to metadata.json.
    """
    out_path = _metadata_json_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not overwrite:
        print(f"[setup_config] metadata.json already exists, leaving as-is: {out_path}")
        return out_path

    data = _default_metadata()

    # Write pretty JSON for readability
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[setup_config] Wrote default metadata.json to: {out_path}")
    return out_path


def main() -> None:
    # Default behavior: do NOT overwrite if user already customized it.
    write_default_metadata_json(overwrite=False)


if __name__ == "__main__":
    main()
