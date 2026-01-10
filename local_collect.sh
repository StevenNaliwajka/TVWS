#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR" && pwd)"

PY="$PROJECT_ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

cd "$PROJECT_ROOT"

# Extra robustness: ensure Codebase/ is importable even if python entry scripts change later.
export PYTHONPATH="$PROJECT_ROOT"

###############################################################################
# local_collect.sh
#
# A "defaults registry" for Codebase/Collection/Local/local_collect.py so you
# don't have to type 20+ flags every run.
#
# Behavior:
#   - This script assembles a set of default args.
#   - Any args you pass to local_collect.sh are appended AFTER defaults.
#     (so user-supplied flags win)
#   - For mutually-exclusive boolean pairs (e.g. --rf-amp / --no-rf-amp),
#     we DO NOT force a default unless you set the corresponding *_MODE variable,
#     to avoid "both flags present" argparse errors.
#
# Tip:
#   Keep your personal defaults in the "DEFAULTS" section below.
###############################################################################

# -----------------------------
# DEFAULTS (edit these)
# -----------------------------

# General
DEF_RUNS="${LOCALCOLLECT_RUNS:-1000}"
DEF_SAMPLE_RATE="${LOCALCOLLECT_SAMPLE_RATE:-20000000}"
DEF_FREQ="${LOCALCOLLECT_FREQ:-491000000}"
DEF_NUM_SAMPLES="${LOCALCOLLECT_NUM_SAMPLES:-20000000}"

# RX/TX gain defaults
DEF_LNA="${LOCALCOLLECT_LNA:-8}"
DEF_VGA="${LOCALCOLLECT_VGA:-8}"
DEF_RX1_LNA="${LOCALCOLLECT_RX1_LNA:-32}"
DEF_RX1_VGA="${LOCALCOLLECT_RX1_VGA:-32}"
DEF_RX2_LNA="${LOCALCOLLECT_RX2_LNA:-16}"
DEF_RX2_VGA="${LOCALCOLLECT_RX2_VGA:-16}"

# Device serial defaults (edit to match the machine)
DEF_RX1_SERIAL="${LOCALCOLLECT_RX1_SERIAL:-0000000000000000930c64dc292c35c3}"
DEF_RX2_SERIAL="${LOCALCOLLECT_RX2_SERIAL:-000000000000000087c867dc2b54905f}"
DEF_TX_SERIAL="${LOCALCOLLECT_TX_SERIAL:-0000000000000000930c64dc2a0a66c}"


# Output
DEF_DATA_ROOT="${LOCALCOLLECT_DATA_ROOT:-$PROJECT_ROOT/Data}"
DEF_TAG="${LOCALCOLLECT_TAG:-}"  # optional
DEF_CONFIG_PATH="${LOCALCOLLECT_CONFIG_PATH:-}"  # optional

# Transmit / trigger / timing
DEF_AMP="${LOCALCOLLECT_AMP:-}"                  # optional (leave blank to use python default)
DEF_RF_AMP_MODE="${LOCALCOLLECT_RF_AMP_MODE:-}"  # "rf" or "no" (blank = don't specify)
DEF_ANT_PWR_MODE="${LOCALCOLLECT_ANT_PWR_MODE:-}" # "on" or "off" (blank = don't specify)
DEF_PULSE="${LOCALCOLLECT_PULSE:-}"              # optional
DEF_SAFETY_MARGIN="${LOCALCOLLECT_SAFETY_MARGIN:-}"           # optional
DEF_RX_READY_TIMEOUT="${LOCALCOLLECT_RX_READY_TIMEOUT:-}"     # optional
DEF_TX_WAIT_TIMEOUT="${LOCALCOLLECT_TX_WAIT_TIMEOUT:-}"       # optional
DEF_NO_HW_TRIGGER="${LOCALCOLLECT_NO_HW_TRIGGER:-1}"          # 1 => add --no-hw-trigger (default)

# Ready patterns (supports multiple --ready-pattern flags).
#
# Option A (env var):
#   export LOCALCOLLECT_READY_PATTERNS='armed,rx1_ready,rx2_ready'
#
# Option B (edit below):
#   LOCALCOLLECT_READY_PATTERNS_DEFAULT=("armed" "rx1_ready" "rx2_ready")
LOCALCOLLECT_READY_PATTERNS_DEFAULT=()
if [[ -n "${LOCALCOLLECT_READY_PATTERNS:-}" ]]; then
  IFS=',' read -r -a LOCALCOLLECT_READY_PATTERNS_DEFAULT <<< "${LOCALCOLLECT_READY_PATTERNS}"
fi

# Disable RX channels by default? (0 = enabled)
DEF_NO_RX1="${LOCALCOLLECT_NO_RX1:-0}"
DEF_NO_RX2="${LOCALCOLLECT_NO_RX2:-0}"


# -----------------------------
# Helpers
# -----------------------------

has_arg() {
  # Usage: has_arg "--flag" "$@"
  local needle="$1"; shift || true
  for a in "$@"; do
    [[ "$a" == "$needle" ]] && return 0
  done
  return 1
}

add_kv_if_missing() {
  # add_kv_if_missing "--flag" "value" "$@"
  local flag="$1" value="$2"; shift 2
  if ! has_arg "$flag" "$@"; then
    ARGS+=("$flag" "$value")
  fi
}

add_flag_if_missing() {
  # add_flag_if_missing "--flag" "$@"
  local flag="$1"; shift
  if ! has_arg "$flag" "$@"; then
    ARGS+=("$flag")
  fi
}

###############################################################################
# Build args
###############################################################################

USER_ARGS=("$@")
ARGS=()

# Key/value args
add_kv_if_missing "--runs"        "$DEF_RUNS"        "${USER_ARGS[@]}"
add_kv_if_missing "--sample-rate" "$DEF_SAMPLE_RATE" "${USER_ARGS[@]}"
add_kv_if_missing "--freq"        "$DEF_FREQ"        "${USER_ARGS[@]}"
add_kv_if_missing "--num-samples" "$DEF_NUM_SAMPLES" "${USER_ARGS[@]}"

add_kv_if_missing "--lna"     "$DEF_LNA"     "${USER_ARGS[@]}"
add_kv_if_missing "--vga"     "$DEF_VGA"     "${USER_ARGS[@]}"
add_kv_if_missing "--rx1-lna" "$DEF_RX1_LNA" "${USER_ARGS[@]}"
add_kv_if_missing "--rx1-vga" "$DEF_RX1_VGA" "${USER_ARGS[@]}"
add_kv_if_missing "--rx2-lna" "$DEF_RX2_LNA" "${USER_ARGS[@]}"
add_kv_if_missing "--rx2-vga" "$DEF_RX2_VGA" "${USER_ARGS[@]}"

add_kv_if_missing "--rx1-serial" "$DEF_RX1_SERIAL" "${USER_ARGS[@]}"
add_kv_if_missing "--rx2-serial" "$DEF_RX2_SERIAL" "${USER_ARGS[@]}"
add_kv_if_missing "--tx-serial"  "$DEF_TX_SERIAL"  "${USER_ARGS[@]}"

add_kv_if_missing "--data-root" "$DEF_DATA_ROOT" "${USER_ARGS[@]}"

if [[ -n "$DEF_TAG" ]]; then
  add_kv_if_missing "--tag" "$DEF_TAG" "${USER_ARGS[@]}"
fi

if [[ -n "$DEF_CONFIG_PATH" ]]; then
  add_kv_if_missing "--config-path" "$DEF_CONFIG_PATH" "${USER_ARGS[@]}"
fi

if [[ -n "$DEF_AMP" ]]; then
  add_kv_if_missing "--amp" "$DEF_AMP" "${USER_ARGS[@]}"
fi

if [[ -n "$DEF_PULSE" ]]; then
  add_kv_if_missing "--pulse" "$DEF_PULSE" "${USER_ARGS[@]}"
fi

if [[ -n "$DEF_SAFETY_MARGIN" ]]; then
  add_kv_if_missing "--safety-margin" "$DEF_SAFETY_MARGIN" "${USER_ARGS[@]}"
fi

if [[ -n "$DEF_RX_READY_TIMEOUT" ]]; then
  add_kv_if_missing "--rx-ready-timeout" "$DEF_RX_READY_TIMEOUT" "${USER_ARGS[@]}"
fi

if [[ -n "$DEF_TX_WAIT_TIMEOUT" ]]; then
  add_kv_if_missing "--tx-wait-timeout" "$DEF_TX_WAIT_TIMEOUT" "${USER_ARGS[@]}"
fi

# Bool-ish toggles (avoid mutual exclusion conflicts)
if [[ "$DEF_NO_RX1" == "1" ]] && ! has_arg "--no-rx1" "${USER_ARGS[@]}"; then
  ARGS+=("--no-rx1")
fi
if [[ "$DEF_NO_RX2" == "1" ]] && ! has_arg "--no-rx2" "${USER_ARGS[@]}"; then
  ARGS+=("--no-rx2")
fi

# --rf-amp / --no-rf-amp (only set if user didn't provide either)
if ! has_arg "--rf-amp" "${USER_ARGS[@]}" && ! has_arg "--no-rf-amp" "${USER_ARGS[@]}"; then
  case "$DEF_RF_AMP_MODE" in
    rf|on|1) ARGS+=("--rf-amp") ;;
    no|off|0) ARGS+=("--no-rf-amp") ;;
    "") : ;; # leave to python default
    *) echo "[local_collect.sh][WARN] Unknown LOCALCOLLECT_RF_AMP_MODE='$DEF_RF_AMP_MODE' (use rf|no)" >&2 ;;
  esac
fi

# --antenna-power / --no-antenna-power
if ! has_arg "--antenna-power" "${USER_ARGS[@]}" && ! has_arg "--no-antenna-power" "${USER_ARGS[@]}"; then
  case "$DEF_ANT_PWR_MODE" in
    on|1|yes|true) ARGS+=("--antenna-power") ;;
    off|0|no|false) ARGS+=("--no-antenna-power") ;;
    "") : ;; # leave to python default
    *) echo "[local_collect.sh][WARN] Unknown LOCALCOLLECT_ANT_PWR_MODE='$DEF_ANT_PWR_MODE' (use on|off)" >&2 ;;
  esac
fi

# --no-hw-trigger
if [[ "$DEF_NO_HW_TRIGGER" == "1" ]] && ! has_arg "--no-hw-trigger" "${USER_ARGS[@]}"; then
  ARGS+=("--no-hw-trigger")
fi

# --ready-pattern (supports multiple). Only apply defaults if user didn't pass any.
if ! has_arg "--ready-pattern" "${USER_ARGS[@]}"; then
  if [[ ${#LOCALCOLLECT_READY_PATTERNS_DEFAULT[@]} -gt 0 ]]; then
    for rp in "${LOCALCOLLECT_READY_PATTERNS_DEFAULT[@]}"; do
      ARGS+=("--ready-pattern" "$rp")
    done
  fi
fi

# Final assembled args (defaults + user overrides)
FINAL_ARGS=("${ARGS[@]}" "${USER_ARGS[@]}")

# Print a quick summary for sanity
echo "[local_collect.sh] Project root : $PROJECT_ROOT" >&2
echo "[local_collect.sh] Using python : $PY" >&2
echo "[local_collect.sh] Script       : $PROJECT_ROOT/Codebase/Collection/Local/local_collect.py" >&2
echo "[local_collect.sh] Args         : ${FINAL_ARGS[*]}" >&2

# Only sudo if not already root
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  exec sudo -E "$PY" "$PROJECT_ROOT/Codebase/Collection/Local/local_collect.py" "${FINAL_ARGS[@]}"
else
  exec "$PY" "$PROJECT_ROOT/Codebase/Collection/Local/local_collect.py" "${FINAL_ARGS[@]}"
fi
