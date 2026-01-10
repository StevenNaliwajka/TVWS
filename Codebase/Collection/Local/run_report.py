#!/usr/bin/env python3
"""
Codebase/Collection/Local/run_report.py

Generate a per-run report file inside each run folder.

Intended usage:
  python3 -m Codebase.Collection.Local.run_report --run-dir <...> --config-path <collection_template.json>

This writes:
  <run-dir>/run_report.json
  <run-dir>/run_report.txt   (optional, enabled by default)

The report is designed to be *robust*: it will still write a report even if some tools
(e.g., hackrf_info) are missing, and it will record those failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _strip_comment_keys(obj: Any) -> Any:
    """
    Recursively drop keys that start with '__comment' anywhere in the config.
    Keeps everything else intact.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("__comment"):
                continue
            out[k] = _strip_comment_keys(v)
        return out
    if isinstance(obj, list):
        return [_strip_comment_keys(x) for x in obj]
    return obj


def _run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout_s: int = 20) -> Dict[str, Any]:
    """
    Run a command and capture output for reporting.
    Never raises; returns a structured dict.
    """
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except Exception as e:
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e}",
        }


def _sha256_file(path: Path, max_bytes: int = 50_000_000) -> Optional[str]:
    """
    Return sha256 for a file, but skip hashing very large files by default.
    """
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return None
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _find_repo_root(start: Path) -> Optional[Path]:
    cur = start.resolve()
    for p in [cur] + list(cur.parents):
        if (p / "Codebase").is_dir():
            return p
    return None


def _parse_hackrf_info_output(txt: str) -> List[Dict[str, Any]]:
    """
    Parse hackrf_info blocks into structured data.
    This is best-effort and tolerant of format changes.
    """
    devices: List[Dict[str, Any]] = []
    if not txt.strip():
        return devices

    lines = txt.splitlines()
    cur: Dict[str, Any] = {}
    in_device = False

    def flush():
        nonlocal cur, in_device
        if cur:
            devices.append(cur)
        cur = {}
        in_device = False

    for line in lines:
        line = line.strip()

        # Start of a device block
        if line.startswith("Found HackRF"):
            flush()
            in_device = True
            cur["found"] = True
            continue

        if not in_device:
            continue

        # Key: Value parsing
        # e.g. "Index: 0"
        if ":" in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            key = k.lower().replace(" ", "_")
            cur[key] = v
            continue

    flush()
    return devices


def _build_expected_commands(config: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    """
    Build expected hackrf_transfer commands from config for reporting.
    (Your runner may use a different invocation; this is informational.)
    """
    rf = config.get("rf", {}) if isinstance(config.get("rf"), dict) else {}
    devices = config.get("devices", {}) if isinstance(config.get("devices"), dict) else {}
    center = rf.get("center_freq_hz")
    srate = rf.get("sample_rate_hz")

    def serial_for(role: str) -> Optional[str]:
        d = devices.get(role)
        if isinstance(d, dict):
            return d.get("serial")
        return None

    def rx_cmd(role: str, role_cfg: Dict[str, Any]) -> Optional[List[str]]:
        if not role_cfg.get("enabled", True):
            return None
        out_name = role_cfg.get("output_filename", f"{role}.iq")
        out_path = run_dir / out_name

        lna = role_cfg.get("lna_db", 0)
        vga = role_cfg.get("vga_db", 0)
        amp = role_cfg.get("amp_enable", False)

        mode = role_cfg.get("capture_mode", "duration")
        n = role_cfg.get("num_samples")
        if mode == "duration":
            dur = float(role_cfg.get("duration_s", 1.0))
            if isinstance(srate, int) and srate > 0:
                n = int(srate * dur)
            else:
                n = None

        cmd = ["hackrf_transfer"]
        ser = serial_for(role)
        if ser:
            cmd += ["-d", str(ser)]
        if center is not None:
            cmd += ["-f", str(center)]
        if srate is not None:
            cmd += ["-s", str(srate)]
        cmd += ["-l", str(lna), "-g", str(vga)]
        if amp:
            cmd += ["-a", "1"]
        if n is not None:
            cmd += ["-n", str(int(n))]
        cmd += ["-r", str(out_path)]
        return cmd

    def tx_cmd(role_cfg: Dict[str, Any]) -> Optional[List[str]]:
        if not role_cfg.get("enabled", True):
            return None
        tx_wave = None
        # try common locations:
        paths = config.get("paths", {}) if isinstance(config.get("paths"), dict) else {}
        tx_wave = paths.get("tx_waveform_path")
        if not tx_wave:
            tx_wave = "Codebase/ReferenceFiles/pilot.tx"

        amp = role_cfg.get("amp_enable", False)
        txvga = role_cfg.get("txvga_db", 0)
        repeat = role_cfg.get("repeat", True)

        cmd = ["hackrf_transfer"]
        ser = serial_for("tx")
        if ser:
            cmd += ["-d", str(ser)]
        if center is not None:
            cmd += ["-f", str(center)]
        if srate is not None:
            cmd += ["-s", str(srate)]
        if amp:
            cmd += ["-a", "1"]
        cmd += ["-x", str(txvga)]
        if repeat:
            cmd += ["-R"]
        cmd += ["-t", str(tx_wave)]
        return cmd

    expected = {
        "rx_1": rx_cmd("rx_1", config.get("rx_1", {}) if isinstance(config.get("rx_1"), dict) else {}),
        "rx_2": rx_cmd("rx_2", config.get("rx_2", {}) if isinstance(config.get("rx_2"), dict) else {}),
        "tx": tx_cmd(config.get("tx", {}) if isinstance(config.get("tx"), dict) else {}),
    }
    # drop Nones
    return {k: v for k, v in expected.items() if v is not None}


def generate_run_report(
    run_dir: Path,
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[Path] = None,
    extra: Optional[Dict[str, Any]] = None,
    write_txt: bool = True,
) -> Tuple[Path, Optional[Path]]:
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    repo_root = _find_repo_root(run_dir) or _find_repo_root(Path.cwd())

    # Load config if needed
    loaded_cfg: Optional[Dict[str, Any]] = None
    config_load_error: Optional[str] = None
    if config is not None:
        loaded_cfg = config
    elif config_path is not None and config_path.exists():
        try:
            loaded_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            config_load_error = f"{type(e).__name__}: {e}"
            loaded_cfg = None

    stripped_cfg = _strip_comment_keys(loaded_cfg) if loaded_cfg is not None else None

    # Basic environment info
    report: Dict[str, Any] = {
        "meta": {
            "generated_utc": _utc_now_iso(),
            "generator": "Codebase.Collection.Local.run_report",
            "python_executable": sys.executable,
            "python_version": sys.version.replace("\n", " "),
            "cwd": str(Path.cwd()),
            "run_dir": str(run_dir),
        },
        "host": {
            "node": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "user": {
            "uid": os.getuid() if hasattr(os, "getuid") else None,
            "gid": os.getgid() if hasattr(os, "getgid") else None,
            "username": os.environ.get("SUDO_USER") or os.environ.get("USER") or os.environ.get("USERNAME"),
            "is_root": (os.geteuid() == 0) if hasattr(os, "geteuid") else None,
        },
        "config": {
            "path": str(config_path) if config_path else None,
            "load_error": config_load_error,
            "data": stripped_cfg,
        },
        "tools": {},
        "hackrf": {},
        "files": [],
        "expected_commands": {},
        "extra": extra or {},
    }

    # Git info (best-effort)
    if repo_root:
        git = {}
        git["repo_root"] = str(repo_root)
        if shutil.which("git"):
            git["head"] = _run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root)
            git["describe"] = _run_cmd(["git", "describe", "--always", "--dirty"], cwd=repo_root)
            git["status_porcelain"] = _run_cmd(["git", "status", "--porcelain"], cwd=repo_root)
        else:
            git["error"] = "git not found in PATH"
        report["git"] = git
    else:
        report["git"] = {"error": "repo root not found (no Codebase/ folder in parents)"}

    # Tool checks
    for tool in ["hackrf_info", "hackrf_transfer"]:
        report["tools"][tool] = {
            "path": shutil.which(tool),
            "present": shutil.which(tool) is not None,
        }

    # HackRF inventory (best-effort)
    if report["tools"]["hackrf_info"]["present"]:
        hi = _run_cmd(["hackrf_info"])
        report["hackrf"]["hackrf_info"] = hi
        report["hackrf"]["devices"] = _parse_hackrf_info_output(hi.get("stdout", ""))
    else:
        report["hackrf"]["hackrf_info"] = {"error": "hackrf_info not found"}

    # Role mapping (if config provides serials)
    roles = {}
    if isinstance(stripped_cfg, dict) and isinstance(stripped_cfg.get("devices"), dict):
        for role in ["tx", "rx_1", "rx_2"]:
            d = stripped_cfg["devices"].get(role)
            if isinstance(d, dict) and d.get("serial"):
                roles[role] = {"serial": d.get("serial"), "index": d.get("index")}
    if roles:
        report["hackrf"]["role_mapping"] = roles

        # Try to annotate found devices with roles
        found = report["hackrf"].get("devices") or []
        if isinstance(found, list) and found:
            serial_to_role = {v.get("serial"): k for k, v in roles.items() if v.get("serial")}
            for dev in found:
                ser = dev.get("serial_number") or dev.get("serial_number_")
                if ser in serial_to_role:
                    dev["role"] = serial_to_role[ser]

    # Expected commands (informational)
    if isinstance(stripped_cfg, dict):
        report["expected_commands"] = _build_expected_commands(stripped_cfg, run_dir)

    # Files in run_dir
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            st = p.stat()
            report["files"].append({
                "path": str(p.relative_to(run_dir)),
                "size_bytes": st.st_size,
                "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
                "sha256": _sha256_file(p),
            })

    # Write JSON
    out_json = run_dir / "run_report.json"
    out_json.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")

    out_txt: Optional[Path] = None
    if write_txt:
        out_txt = run_dir / "run_report.txt"
        out_txt.write_text(_render_txt(report), encoding="utf-8")

    return out_json, out_txt


def _render_txt(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    meta = report.get("meta", {})
    lines.append("TVWS Local Collect - Run Report")
    lines.append("=" * 34)
    lines.append(f"Generated (UTC): {meta.get('generated_utc')}")
    lines.append(f"Run dir       : {meta.get('run_dir')}")
    lines.append(f"Python        : {meta.get('python_executable')}")
    lines.append(f"Python ver    : {meta.get('python_version')}")
    lines.append("")

    host = report.get("host", {})
    lines.append("Host")
    lines.append("-" * 10)
    lines.append(f"Node     : {host.get('node')}")
    lines.append(f"System   : {host.get('system')} {host.get('release')}")
    lines.append(f"Machine  : {host.get('machine')}")
    lines.append("")

    tools = report.get("tools", {})
    lines.append("Tools")
    lines.append("-" * 10)
    for t, info in tools.items():
        lines.append(f"{t:14} present={info.get('present')} path={info.get('path')}")
    lines.append("")

    git = report.get("git", {})
    lines.append("Git")
    lines.append("-" * 10)
    if "error" in git:
        lines.append(f"Git error: {git.get('error')}")
    else:
        head = (git.get("head", {}) or {}).get("stdout", "").strip()
        desc = (git.get("describe", {}) or {}).get("stdout", "").strip()
        lines.append(f"Repo root: {git.get('repo_root')}")
        lines.append(f"HEAD     : {head}")
        lines.append(f"Describe : {desc}")
        status = (git.get("status_porcelain", {}) or {}).get("stdout", "").strip()
        if status:
            lines.append("Dirty files:")
            lines.extend([f"  {x}" for x in status.splitlines()])
        else:
            lines.append("Working tree clean.")
    lines.append("")

    hackrf = report.get("hackrf", {})
    lines.append("HackRF devices")
    lines.append("-" * 16)
    devs = hackrf.get("devices", [])
    if not devs:
        lines.append("No devices parsed (hackrf_info missing or no HackRFs found).")
    else:
        for d in devs:
            role = d.get("role", "")
            idx = d.get("index", d.get("index_", ""))
            ser = d.get("serial_number", d.get("serial_number_", ""))
            fw = d.get("firmware_version", "")
            bid = d.get("board_id_number", "")
            lines.append(f"- {role or 'device'} | idx={idx} | serial={ser} | fw={fw} | board={bid}")
    lines.append("")

    exp = report.get("expected_commands", {})
    if exp:
        lines.append("Expected hackrf_transfer commands (informational)")
        lines.append("-" * 48)
        for role, cmd in exp.items():
            lines.append(f"{role}: {' '.join(cmd)}")
        lines.append("")

    lines.append("Files in run dir")
    lines.append("-" * 16)
    for f in report.get("files", []):
        lines.append(f"- {f.get('path')} ({f.get('size_bytes')} bytes) sha256={f.get('sha256') or 'skipped'}")

    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate per-run report files (JSON/TXT) inside a run directory.")
    ap.add_argument("--run-dir", required=True, help="Path to the run folder (e.g., .../run_0001).")
    ap.add_argument("--config-path", default=None, help="Path to your user-managed config JSON (template).")
    ap.add_argument("--no-txt", action="store_true", help="Disable generating run_report.txt")
    ap.add_argument("--extra", action="append", default=[], help="Extra key=value pairs to include (repeatable).")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    ns = _parse_args(argv)

    run_dir = Path(ns.run_dir)

    config_path = Path(ns.config_path).resolve() if ns.config_path else None
    extra: Dict[str, Any] = {}
    for item in ns.extra:
        if "=" in item:
            k, v = item.split("=", 1)
            extra[k.strip()] = v.strip()
        else:
            extra[item.strip()] = True

    generate_run_report(
        run_dir=run_dir,
        config=None,
        config_path=config_path,
        extra=extra,
        write_txt=not ns.no_txt,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
