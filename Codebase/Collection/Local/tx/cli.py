from __future__ import annotations
from typing import List, Optional
from Codebase.Collection.Local.tx.controller_lib import main as tx_main

def main(argv: Optional[List[str]] = None) -> int:
    return tx_main(argv)

if __name__ == "__main__":
    raise SystemExit(main())
