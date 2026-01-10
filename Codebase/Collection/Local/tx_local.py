#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

def _ensure_repo_root_on_syspath() -> None:
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "Codebase").is_dir():
            sys.path.insert(0, str(parent))
            return
    sys.path.insert(0, str(here.parents[3]))

_ensure_repo_root_on_syspath()

from Codebase.Collection.Local.tx.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
