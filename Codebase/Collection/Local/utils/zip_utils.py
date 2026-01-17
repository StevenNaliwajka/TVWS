from __future__ import annotations

import shutil
from pathlib import Path


def _zip_session_dir(session_dir: Path, *, delete_original: bool = False) -> Path:
    session_dir = session_dir.resolve()
    if not session_dir.exists() or not session_dir.is_dir():
        raise FileNotFoundError(f"Session dir not found: {session_dir}")

    zip_path = session_dir.parent / f"{session_dir.name}.zip"

    if zip_path.exists():
        zip_path.unlink()

    base_name = str(zip_path.with_suffix(""))

    shutil.make_archive(
        base_name=base_name,
        format="zip",
        root_dir=str(session_dir.parent),
        base_dir=session_dir.name,
    )

    if delete_original:
        shutil.rmtree(session_dir)

    return zip_path
