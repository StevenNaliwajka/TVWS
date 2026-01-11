# Codebase/MetaData/metadata_object.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"metadata.json not found at: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object at: {path}")
    return data


class MetaDataObj:
    def __init__(self, json_path: str | Path | None = None):
        # This file lives at: PROJECT_ROOT/Codebase/MetaData/metadata_object.py
        # parents[2] => PROJECT_ROOT  (MetaData -> Codebase -> PROJECT_ROOT)
        project_root = Path(__file__).resolve().parents[2]

        # Prefer PROJECT_ROOT/Config/metadata.json, but allow fallback to Codebase/Config.
        candidate_defaults = [
            project_root / "Config" / "metadata.json",
            project_root / "Codebase" / "Config" / "metadata.json",
        ]

        if json_path is None:
            # pick the first one that exists, else keep the preferred one so error msg is clear
            self.json_path = next((p for p in candidate_defaults if p.exists()), candidate_defaults[0])
        else:
            jp = Path(json_path)

            # If user passed a relative path, interpret it relative to PROJECT_ROOT
            if not jp.is_absolute():
                jp = project_root / jp

            self.json_path = jp

        data = _load_json(self.json_path)

        # Store the raw dict too (helpful for debugging / iteration)
        self.data = data

        # Expose every key in metadata.json as an attribute
        for k, v in data.items():
            setattr(self, k, v)

        # Defaults / computed fields
        self.edge_percentage = float(data.get("edge_percentage", 0.90))

        # relative tof is stored as a 2D array w/ (FT, NS)
        self.average_relative_tof = None

        # Optional sanity checks for common numeric fields (keeps bugs loud)
        for k in ("baseband_hz", "sync_hz", "signal_tx_hz", "sample_rate_hz", "qty_peaks"):
            if hasattr(self, k) and getattr(self, k) is not None:
                setattr(self, k, int(getattr(self, k)))
