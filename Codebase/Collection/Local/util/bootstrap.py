from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional

def add_project_root(file_path: str) -> Path:
    '''
    Ensure the repo root is in sys.path so imports like:
        from Codebase.Collection.Local... work
    even when running scripts by absolute path.

    Repo layout assumed:
        <root>/Codebase/Collection/Local/<this_file_or_script>
    '''
    p = Path(file_path).resolve()
    # Walk up until we find "Codebase", then take its parent as root.
    for parent in [p] + list(p.parents):
        if parent.name == "Codebase":
            root = parent.parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return root

    # Fallback: assume scripts live at <root>/Codebase/Collection/Local/*.py
    # so go up 3 parents from Local scripts.
    root = p.parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
