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

        # Required location per your request:
        default_path = project_root / "Config" / "metadata.json"
        self.json_path = Path(json_path) if json_path is not None else default_path

        data = _load_json(self.json_path)

        # Store the raw dict too (helpful for debugging / iteration)
        self.data = data


        ## relative tof is stored as a 2D array w/
        ## 10, 3900
        ## 15, 5999
        ## ..., ...
        ## Stores FT, NS
        self.average_relative_tof = None


        # Expose every key in metadata.json as an attribute
        for k, v in data.items():
            setattr(self, k, v)

        # Optional sanity checks for common numeric fields (keeps bugs loud)
        for k in ("baseband_hz", "sync_hz", "signal_tx_hz", "sample_rate_hz"):
            if hasattr(self, k):
                setattr(self, k, int(getattr(self, k)))
