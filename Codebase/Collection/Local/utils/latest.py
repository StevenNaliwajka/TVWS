from __future__ import annotations

import shutil
from pathlib import Path


def _update_latest_dir(*, latest_dir: Path, run_dir: Path, session_dir: Path, run_name: str) -> None:
    latest_dir = latest_dir.resolve()
    run_dir = run_dir.resolve()
    session_dir = session_dir.resolve()

    if latest_dir.exists():
        shutil.rmtree(latest_dir, ignore_errors=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    for p in run_dir.iterdir():
        dst = latest_dir / p.name
        if p.is_dir():
            shutil.copytree(p, dst)
        else:
            shutil.copy2(p, dst)

    cfg_path = session_dir / "session_config.json"
    if cfg_path.exists():
        shutil.copy2(cfg_path, latest_dir / "session_config.json")

    (latest_dir / "LATEST_SOURCE.txt").write_text(
        f"session_dir={session_dir}\nrun_name={run_name}\nrun_dir={run_dir}\n",
        encoding="utf-8",
    )
