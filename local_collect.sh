#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------
# local_collect.sh (BULK, single machine)
#
# Assumes THREE HackRFs are plugged into this ONE machine:
#   - RX1 HackRF (captures to *_capture_1.iq)
#   - RX2 HackRF (captures to *_capture_2.iq)
#   - TX  HackRF (transmits pilot.iq)
#
# This script loops N runs, creates:
#   Data/collect_<timestamp>/run_0001, run_0002, ...
# And calls Codebase/Collection/Local/tx_local.py for each run.
# ---------------------------------------

# ==========================
# User-configurable defaults
# ==========================
# If you have 3 HackRFs plugged into one machine, set their serials here so you
# don't have to pass --rx1-serial/--rx2-serial/--tx-serial every run.
# Leave blank ("") if you prefer to require passing flags.
RX1_SERIAL_DEFAULT="000000000000000087c867dc2b54905f"
RX2_SERIAL_DEFAULT="0000000000000000930c64dc2a0a66c3"
TX_SERIAL_DEFAULT="0000000000000000930c64dc292c35c3"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

VENV_DIR="$PROJECT_ROOT/.venv"
COLLECT_DIR="$PROJECT_ROOT/Codebase/Collection/Local"
RX1_PY="$COLLECT_DIR/rx_1_local.py"
RX2_PY="$COLLECT_DIR/rx_2_local.py"
TX_PY="$COLLECT_DIR/tx_local.py"
DATA_ROOT="$PROJECT_ROOT/Data"

# Defaults (override via flags below)
RUNS=10
FREQ=520000000
SR=20000000
NSAMPLES=7000
LNA=8
VGA=8
RX1_LNA=""
RX1_VGA=""
RX2_LNA=""
RX2_VGA=""
AMP=45
PULSE="$PROJECT_ROOT/Codebase/Collection/pilot.iq"
SAFETY_MARGIN="1.0"
SLEEP_BETWEEN="0.0"
RX_READY_TIMEOUT="0.5"
TX_WAIT_TIMEOUT="10.0"
NO_HW_TRIGGER=0

RX1_SERIAL=""
RX2_SERIAL=""
TX_SERIAL=""

usage() {
  cat <<EOF
Usage: sudo bash local_collect.sh [options]

Options:
  --runs N
  --freq HZ
  --sr HZ
  --nsamples N
  --lna N
  --vga N
  --rx1-lna N
  --rx1-vga N
  --rx2-lna N
  --rx2-vga N
  --amp N
  --pulse PATH
  --data-root PATH
  --safety-margin SECONDS
  --sleep-between SECONDS
  --rx-ready-timeout SECONDS
  --tx-wait-timeout SECONDS
  --no-hw-trigger

  --rx1-serial SERIAL
  --rx2-serial SERIAL
  --tx-serial  SERIAL

  --list-devices    (runs tx_local.py --list-devices and exits)

Notes:
  - If you have >1 HackRF plugged in, you SHOULD pass serials so each process grabs the right device.
  - Get serials by running:  sudo bash local_collect.sh --list-devices
EOF
}

# Parse args
LIST_DEVICES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs) RUNS="$2"; shift 2 ;;
    --freq) FREQ="$2"; shift 2 ;;
    --sr) SR="$2"; shift 2 ;;
    --nsamples) NSAMPLES="$2"; shift 2 ;;
    --lna) LNA="$2"; shift 2 ;;
    --vga) VGA="$2"; shift 2 ;;
    --rx1-lna) RX1_LNA="$2"; shift 2 ;;
    --rx1-vga) RX1_VGA="$2"; shift 2 ;;
    --rx2-lna) RX2_LNA="$2"; shift 2 ;;
    --rx2-vga) RX2_VGA="$2"; shift 2 ;;
    --amp) AMP="$2"; shift 2 ;;
    --pulse) PULSE="$2"; shift 2 ;;
    --data-root) DATA_ROOT="$2"; shift 2 ;;
    --safety-margin) SAFETY_MARGIN="$2"; shift 2 ;;
    --sleep-between) SLEEP_BETWEEN="$2"; shift 2 ;;
    --rx-ready-timeout) RX_READY_TIMEOUT="$2"; shift 2 ;;
    --tx-wait-timeout) TX_WAIT_TIMEOUT="$2"; shift 2 ;;
    --no-hw-trigger) NO_HW_TRIGGER=1; shift 1 ;;
    --rx1-serial) RX1_SERIAL="$2"; shift 2 ;;
    --rx2-serial) RX2_SERIAL="$2"; shift 2 ;;
    --tx-serial) TX_SERIAL="$2"; shift 2 ;;
    --list-devices) LIST_DEVICES=1; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[local_collect.sh][ERROR] Unknown arg: $1"; usage; exit 2 ;;
  esac
done

# Apply default serials if not provided via CLI flags
RX1_SERIAL="${RX1_SERIAL:-$RX1_SERIAL_DEFAULT}"
RX2_SERIAL="${RX2_SERIAL:-$RX2_SERIAL_DEFAULT}"
TX_SERIAL="${TX_SERIAL:-$TX_SERIAL_DEFAULT}"


PY="$VENV_DIR/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "[local_collect.sh][ERROR] venv python not found at: $PY"
  echo "  Create it or adjust VENV_DIR in this script."
  exit 1
fi
if [[ ! -f "$TX_PY" ]]; then
  echo "[local_collect.sh][ERROR] tx_local.py not found at: $TX_PY"
  exit 1
fi

if [[ ! -f "$RX1_PY" ]]; then
  echo "[local_collect.sh][WARN] rx_1_local.py not found at: $RX1_PY"
  echo "[local_collect.sh][WARN] tx_local.py may fail if it imports RX1 script by path."
fi

if [[ ! -f "$RX2_PY" ]]; then
  echo "[local_collect.sh][WARN] rx_2_local.py not found at: $RX2_PY"
  echo "[local_collect.sh][WARN] tx_local.py may fail if it imports RX2 script by path."
fi


echo "[local_collect.sh] Project root : $PROJECT_ROOT"
echo "[local_collect.sh] Using python : $PY"
echo "[local_collect.sh] TX script    : $TX_PY"
echo "[local_collect.sh] RX1 script   : $RX1_PY"
echo "[local_collect.sh] RX2 script   : $RX2_PY"
echo "[local_collect.sh] Data root    : $DATA_ROOT"
echo "[local_collect.sh] Runs         : $RUNS"
echo "[local_collect.sh] Freq/SR      : $FREQ / $SR"
echo "[local_collect.sh] Nsamps        : $NSAMPLES"
echo "[local_collect.sh] Gains (base)  : LNA=$LNA VGA=$VGA"
echo "[local_collect.sh] Serials       : rx1='${RX1_SERIAL}' rx2='${RX2_SERIAL}' tx='${TX_SERIAL}'"
echo ""

mkdir -p "$DATA_ROOT"

if [[ "$LIST_DEVICES" -eq 1 ]]; then
  echo "[local_collect.sh] Listing HackRF devices via hackrf_info:"
  sudo -E "$PY" "$TX_PY" --list-devices
  exit $?
fi

# Session folder
SESSION_TS="$(date -u +%Y-%m-%dT%H-%M-%S)_$(printf "%04d" $(( (10#$(date -u +%N)) / 100000 )))"
SESSION_DIR="$DATA_ROOT/collect_${SESSION_TS}"
mkdir -p "$SESSION_DIR"

INDEX_CSV="$SESSION_DIR/index.csv"
SESSION_JSON="$SESSION_DIR/session.json"

echo "run_id,run_dir,exit_code,rx1_iq,rx2_iq" > "$INDEX_CSV"

# Save session meta
cat > "$SESSION_JSON" <<JSON
{
  "session_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "runs": $RUNS,
  "freq_hz": $FREQ,
  "sample_rate_hz": $SR,
  "nsamples": $NSAMPLES,
  "lna": $LNA,
  "vga": $VGA,
  "rx1_lna": "${RX1_LNA:-}",
  "rx1_vga": "${RX1_VGA:-}",
  "rx2_lna": "${RX2_LNA:-}",
  "rx2_vga": "${RX2_VGA:-}",
  "amp": $AMP,
  "pulse": "$PULSE",
  "rx_ready_timeout_s": $RX_READY_TIMEOUT,
  "tx_wait_timeout_s": $TX_WAIT_TIMEOUT,
  "safety_margin_s": $SAFETY_MARGIN,
  "sleep_between_s": $SLEEP_BETWEEN,
  "no_hw_trigger": $NO_HW_TRIGGER,
  "rx1_serial": "${RX1_SERIAL:-}",
  "rx2_serial": "${RX2_SERIAL:-}",
  "tx_serial": "${TX_SERIAL:-}"
}
JSON

FAILS=0

for i in $(seq 1 "$RUNS"); do
  RUN_ID="run_$(printf "%04d" "$i")"
  RUN_DIR="$SESSION_DIR/$RUN_ID"
  mkdir -p "$RUN_DIR"

  echo "[local_collect.sh] ===== $RUN_ID / $RUNS ====="
  echo "[local_collect.sh] Run dir: $RUN_DIR"
  echo "[local_collect.sh] Start  : $(date -u +%Y-%m-%dT%H:%M:%SZ)"

  # Build tx_local.py args
  TX_ARGS=(
    --save-dir "$RUN_DIR"
    --freq "$FREQ"
    --sr "$SR"
    --nsamples "$NSAMPLES"
    --lna "$LNA"
    --vga "$VGA"
    --amp "$AMP"
    --pulse "$PULSE"
    --rx-ready-timeout "$RX_READY_TIMEOUT"
    --tx-wait-timeout "$TX_WAIT_TIMEOUT"
    --safety-margin "$SAFETY_MARGIN"
  )

  if [[ -n "$RX1_LNA" ]]; then TX_ARGS+=( --rx1-lna "$RX1_LNA" ); fi
  if [[ -n "$RX1_VGA" ]]; then TX_ARGS+=( --rx1-vga "$RX1_VGA" ); fi
  if [[ -n "$RX2_LNA" ]]; then TX_ARGS+=( --rx2-lna "$RX2_LNA" ); fi
  if [[ -n "$RX2_VGA" ]]; then TX_ARGS+=( --rx2-vga "$RX2_VGA" ); fi

  if [[ "$NO_HW_TRIGGER" -eq 1 ]]; then TX_ARGS+=( --no-hw-trigger ); fi

  if [[ -n "$RX1_SERIAL" ]]; then TX_ARGS+=( --rx1-serial "$RX1_SERIAL" ); fi
  if [[ -n "$RX2_SERIAL" ]]; then TX_ARGS+=( --rx2-serial "$RX2_SERIAL" ); fi
  if [[ -n "$TX_SERIAL"  ]]; then TX_ARGS+=( --tx-serial  "$TX_SERIAL"  ); fi

  echo "[local_collect.sh] tx_local.py args  : ${TX_ARGS[*]}"

  set +e
  sudo -E "$PY" "$TX_PY" "${TX_ARGS[@]}"
  RC=$?
  set -e

  RX1_IQ="$(ls -1 "$RUN_DIR"/*_capture_1.iq 2>/dev/null | head -n 1 || true)"
  RX2_IQ="$(ls -1 "$RUN_DIR"/*_capture_2.iq 2>/dev/null | head -n 1 || true)"

  echo "$RUN_ID,$RUN_DIR,$RC,$RX1_IQ,$RX2_IQ" >> "$INDEX_CSV"

  if [[ "$RC" -ne 0 ]]; then
    echo "[local_collect.sh] $RUN_ID FAILED (rc=$RC)"
    FAILS=$((FAILS+1))
  else
    echo "[local_collect.sh] $RUN_ID OK"
  fi

  if [[ "$(printf '%.6f' "$SLEEP_BETWEEN")" != "0.000000" ]]; then
    sleep "$SLEEP_BETWEEN"
  fi
  echo ""
done

echo "[local_collect.sh] Done."
echo "[local_collect.sh] Session: $SESSION_DIR"
echo "[local_collect.sh] Failures: $FAILS"
echo "[local_collect.sh] Index: $INDEX_CSV"
echo "[local_collect.sh] Session meta: $SESSION_JSON"
