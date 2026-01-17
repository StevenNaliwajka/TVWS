#!/usr/bin/env python3
from __future__ import annotations

from Codebase.Collection.Local.app.cli import parse_args
from Codebase.Collection.Local.app.collector import run_collection


def main() -> int:
    cfg = parse_args()
    run_collection(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
