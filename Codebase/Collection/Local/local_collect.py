#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

def _ensure_repo_root_on_syspath() -> None:
    """
    Add repo root to sys.path so `import Codebase...` works even when running by path.
    Repo root is the folder that contains the `Codebase/` directory.
    """
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "Codebase").is_dir():
            sys.path.insert(0, str(parent))
            return
    # Fallback (shouldn't happen): assume <root>/Codebase/Collection/Local/local_collect.py
    sys.path.insert(0, str(here.parents[3]))

_ensure_repo_root_on_syspath()

from Codebase.Collection.Local.collect.session_runner import main

if __name__ == "__main__":
    raise SystemExit(main())
