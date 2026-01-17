from __future__ import annotations

import os
import time
from datetime import datetime


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _unique_session_name(tag: str) -> str:
    suffix = f"{os.getpid()}_{(time.monotonic_ns() % 10_000):04d}"
    base = f"Collection_{_now_stamp()}_{suffix}"
    return f"{base}_{tag}" if tag else base
