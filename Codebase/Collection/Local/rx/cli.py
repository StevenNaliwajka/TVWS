from __future__ import annotations
from typing import List, Optional
from Codebase.Collection.Local.rx.capture_ready import main as rx_main

def main(argv: Optional[List[str]] = None) -> int:
    return rx_main(argv)

if __name__ == "__main__":
    raise SystemExit(main())
