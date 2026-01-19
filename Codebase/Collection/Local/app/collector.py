from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from Codebase.Collection.Local.app.config import RunConfig
from Codebase.Collection.Local.hackrf.checks import _check_hackrfs_present, _require_tool
from Codebase.Collection.Local.hackrf.commands import build_rx_cmd, build_tx_cmd
from Codebase.Collection.Local.hackrf.process import _popen_to_files, _terminate, _wait_for_log_text
from Codebase.Collection.Local.utils.latest import _update_latest_dir
from Codebase.Collection.Local.utils.paths import _unique_session_name
from Codebase.Collection.Local.utils.zip_utils import _zip_session_dir


def run_collection(cfg: RunConfig) -> Path:
    project_root = Path(__file__).resolve().parents[3]

    data_root = Path(cfg.data_root).resolve().parents[1]
    data_root = data_root/ "Data"
    pulse_path = Path(cfg.pulse_path).resolve()

    session_dir = data_root / _unique_session_name(cfg.tag)
    session_dir.mkdir(parents=True, exist_ok=True)

    (session_dir / "session_config.json").write_text(
        json.dumps(asdict(cfg), indent=2),
        encoding="utf-8",
    )

    max_retries = int(getattr(cfg, "max_run_retries", 3))
    retry_backoff_s = float(getattr(cfg, "retry_backoff_s", 0.25))

    print(f"[INFO] Project root : {project_root}")
    print(f"[INFO] Data root    : {data_root}")
    print(f"[INFO] Pulse IQ     : {pulse_path}")
    print(f"[INFO] Session dir  : {session_dir}")
    print(f"[INFO] Runs         : {cfg.runs}")
    print(f"[INFO] HW trigger   : {cfg.hw_trigger}")
    print(f"[INFO] Retries      : max_retries={max_retries} backoff_s={retry_backoff_s}")
    print(
        f"[INFO] RX gains     : global LNA/VGA={cfg.lna_db}/{cfg.vga_db}  |  "
        f"RX1={cfg.rx1_lna_db}/{cfg.rx1_vga_db}  RX2={cfg.rx2_lna_db}/{cfg.rx2_vga_db}"
    )

    if not pulse_path.exists():
        raise SystemExit(f"[ERROR] Pulse IQ file not found: {pulse_path}")

    _require_tool("hackrf_transfer")
    _require_tool("hackrf_info")
    _check_hackrfs_present([cfg.rx1_serial, cfg.rx2_serial, cfg.tx_serial])

    for i in range(1, cfg.runs + 1):
        run_name = f"run_{i:04d}"
        run_dir = session_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        rx1_iq_final = run_dir / "rx1.iq"
        rx2_iq_final = run_dir / "rx2.iq"
        rx1_log_final = run_dir / "rx1.log"
        rx2_log_final = run_dir / "rx2.log"
        tx_log_final = run_dir / "tx.log"

        print(f"\n[INFO] ===== {run_name} / {cfg.runs} =====")
        print(f"[INFO] Run dir: {run_dir}")

        for attempt in range(1, max_retries + 1):
            print(f"[INFO] Attempt {attempt}/{max_retries}")

            rx1_iq_try = run_dir / f"rx1_try{attempt}.iq"
            rx2_iq_try = run_dir / f"rx2_try{attempt}.iq"
            rx1_log = run_dir / f"rx1_try{attempt}.log"
            rx2_log = run_dir / f"rx2_try{attempt}.log"
            tx_log = run_dir / f"tx_try{attempt}.log"

            for p in (rx1_iq_try, rx2_iq_try, rx1_log, rx2_log, tx_log):
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

            rx1_cmd = build_rx_cmd(
                out_path=rx1_iq_try,
                serial=cfg.rx1_serial,
                sample_rate_hz=cfg.sample_rate_hz,
                freq_hz=cfg.freq_hz,
                num_samples=cfg.num_samples,
                lna_db=cfg.rx1_lna_db,
                vga_db=cfg.rx1_vga_db,
                hw_trigger=cfg.hw_trigger,
            )
            rx2_cmd = build_rx_cmd(
                out_path=rx2_iq_try,
                serial=cfg.rx2_serial,
                sample_rate_hz=cfg.sample_rate_hz,
                freq_hz=cfg.freq_hz,
                num_samples=cfg.num_samples,
                lna_db=cfg.rx2_lna_db,
                vga_db=cfg.rx2_vga_db,
                hw_trigger=cfg.hw_trigger,
            )
            tx_cmd = build_tx_cmd(
                iq_path=pulse_path,
                serial=cfg.tx_serial,
                sample_rate_hz=cfg.sample_rate_hz,
                freq_hz=cfg.freq_hz,
                amp_db=cfg.tx_amp_db,
                rf_amp=cfg.rf_amp,
                antenna_power=cfg.antenna_power,
            )

            print("[INFO] RX1 cmd:", " ".join(rx1_cmd))
            print("[INFO] RX2 cmd:", " ".join(rx2_cmd))
            print("[INFO] TX  cmd:", " ".join(tx_cmd))

            rx1 = None
            rx2 = None
            tx = None

            try:
                rx1 = _popen_to_files(rx1_cmd, rx1_log)
                rx2 = _popen_to_files(rx2_cmd, rx2_log)

                if cfg.hw_trigger:
                    needles = ["Waiting for trigger", "READY"]
                    ok1 = _wait_for_log_text(
                        rx1_log,
                        needles=needles,
                        timeout_s=cfg.tx_wait_timeout_s,
                        min_delay_s=cfg.rx_ready_timeout_s,
                    )
                    ok2 = _wait_for_log_text(
                        rx2_log,
                        needles=needles,
                        timeout_s=cfg.tx_wait_timeout_s,
                        min_delay_s=0.0,
                    )
                    if not (ok1 and ok2):
                        raise RuntimeError(
                            "RX did not reach 'Waiting for trigger' state in time. "
                            "Check trigger wiring and that RX is started with -H."
                        )
                else:
                    time.sleep(cfg.rx_ready_timeout_s)

                tx = _popen_to_files(tx_cmd, tx_log)

                tx.wait(timeout=cfg.tx_wait_timeout_s)
                if tx.returncode != 0:
                    raise RuntimeError(f"TX failed (return code {tx.returncode}). See: {tx_log}")

                rx_deadline = max(2.0, cfg.safety_margin_s + 2.0)
                rx1.wait(timeout=rx_deadline)
                rx2.wait(timeout=rx_deadline)

                if rx1.returncode != 0:
                    raise RuntimeError(f"RX1 failed (return code {rx1.returncode}). See: {rx1_log}")
                if rx2.returncode != 0:
                    raise RuntimeError(f"RX2 failed (return code {rx2.returncode}). See: {rx2_log}")

                # Promote logs
                try:
                    rx1_log_final.write_text(rx1_log.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                except Exception:
                    pass
                try:
                    rx2_log_final.write_text(rx2_log.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                except Exception:
                    pass
                try:
                    tx_log_final.write_text(tx_log.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                except Exception:
                    pass

                # Promote IQ
                if rx1_iq_final.exists():
                    try:
                        rx1_iq_final.unlink()
                    except Exception:
                        pass
                if rx2_iq_final.exists():
                    try:
                        rx2_iq_final.unlink()
                    except Exception:
                        pass

                rx1_iq_try.replace(rx1_iq_final)
                rx2_iq_try.replace(rx2_iq_final)

                # Success! break attempts loop
                break

            except Exception as e:
                print(f"[ERROR] {run_name} attempt {attempt}: {e}")

                try:
                    if rx1 is not None:
                        _terminate(rx1, "rx1")
                except Exception:
                    pass
                try:
                    if rx2 is not None:
                        _terminate(rx2, "rx2")
                except Exception:
                    pass
                try:
                    if tx is not None:
                        _terminate(tx, "tx")
                except Exception:
                    pass

                if attempt < max_retries:
                    print(f"[WARN] Retrying {run_name} after {retry_backoff_s:.2f}s...\n")
                    time.sleep(retry_backoff_s)
                else:
                    print(f"[ERROR] {run_name}: exceeded max retries ({max_retries}). Aborting session.")
                    raise SystemExit(1)

        rx1_size = rx1_iq_final.stat().st_size if rx1_iq_final.exists() else 0
        rx2_size = rx2_iq_final.stat().st_size if rx2_iq_final.exists() else 0
        print(f"[INFO] RX1 IQ bytes: {rx1_size}")
        print(f"[INFO] RX2 IQ bytes: {rx2_size}")

        if i == 1:
            latest_dir = data_root / "Latest"
            _update_latest_dir(
                latest_dir=latest_dir,
                run_dir=run_dir,
                session_dir=session_dir,
                run_name=run_name,
            )
            print(f"[INFO] Updated Latest folder: {latest_dir}")

        if rx1_size == 0 or rx2_size == 0:
            print(
                "[WARN] One or both RX files are empty.\n"
                "       If you are using -H, this usually means the trigger was never received.\n"
                "       Check wiring between TX trigger-out and RX trigger-in."
            )

    print(f"\n[INFO] Done. Session saved at: {session_dir}")

    zip_path = _zip_session_dir(session_dir)
    print(f"[INFO] Zipped session : {zip_path}")

    return session_dir
