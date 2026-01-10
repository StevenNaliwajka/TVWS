from __future__ import annotations
from datetime import datetime

def utc_stamp() -> str:
    # Human-friendly timestamp (UTC) used in logs.
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def utc_timestamp_for_filename() -> str:
    # File-friendly timestamp (UTC) used in filenames.
    dt = datetime.utcnow()
    return f"{dt:%Y-%m-%dT%H-%M-%S}_{dt.microsecond // 100:04d}"
