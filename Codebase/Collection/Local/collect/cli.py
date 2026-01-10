from __future__ import annotations
from typing import List, Optional
from Codebase.Collection.Local.collect.session_runner import main as collect_main

def main(argv: Optional[List[str]] = None) -> int:
    return collect_main(argv)

if __name__ == "__main__":
    raise SystemExit(main())
