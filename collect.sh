#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------
# collect.sh (BULK)
# Runs Codebase/Collection/tx.py N times and stores each run in a unique folder under /Data/
# ---------------------------------------

# Resolve PROJECT_ROOT as the directory containing this script
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

VENV_DIR="$PROJECT_ROOT/.venv"
TX_PY="$PROJECT_ROOT/Codebase/Collection/tx.py"

# ---- Defaults ----
RUNS=100
PREFIX="collect"
DATA_ROOT="$PROJECT_ROOT/Data"
SLEEP_BETWEEN="0"
FAIL_FAST=0

# Default tx.py args (used only if no tx args are provided on the collect.sh command line)
# This implements:
#   python3 tx.py --rf-amp --lna 32 --vga 32 --rx2-lna 16 --rx2-vga 16
DEFAULT_TX_ARGS=(--rf-amp --lna 40 --vga 38 --rx2-lna 16 --rx2-vga 16)

# Everything not recognized here will be passed through to tx.py
TX_ARGS=()

usage() {
  cat <<EOF
Usage:
  ./collect.sh [options] [-- <tx.py args...>]

Options:
  --runs N            Number of runs (default: 100)
  --data-root PATH    Root output directory (default: PROJECT_ROOT/Data)
  --prefix NAME       Session folder prefix (default: collect)
  --sleep SEC         Sleep between runs (default: 0)
  --fail-fast         Stop on the first failure (default: keep going)

Examples:
  ./collect.sh
  ./collect.sh --runs 100 --data-root /opt/TVWS/Data
  ./collect.sh --runs 20 -- --freq 520000000 --sr 20000000 --nsamples 25000 --lna 16 --vga 16 --ready-timeout 0.5 --hw-trigger
EOF
}

# ---- Parse args ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs)        RUNS="${2:-}"; shift 2 ;;
    --data-root)   DATA_ROOT="${2:-}"; shift 2 ;;
    --prefix)      PREFIX="${2:-}"; shift 2 ;;
    --sleep)       SLEEP_BETWEEN="${2:-}"; shift 2 ;;
    --fail-fast)   FAIL_FAST=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    --)            shift; TX_ARGS+=("$@"); break ;;
    *)             TX_ARGS+=("$1"); shift ;;
  esac
done


# ---- Apply default tx.py args (only when none were supplied) ----
if [[ ${#TX_ARGS[@]} -eq 0 ]]; then
  TX_ARGS=("${DEFAULT_TX_ARGS[@]}")
fi

# ---- Validate paths ----
if [[ ! -d "$VENV_DIR" ]]; then
  echo "[ERROR] .venv not found at: $VENV_DIR" >&2
  exit 1
fi

if [[ ! -f "$TX_PY" ]]; then
  echo "[ERROR] tx.py not found at: $TX_PY" >&2
  exit 1
fi

# ---- Activate venv ----
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

PY="$VENV_DIR/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "[ERROR] venv python not executable: $PY" >&2
  exit 1
fi

# ---- Helpers ----
utc_now_compact() {
  local ns
  ns="$(date -u +%N | cut -c1-4)"
  echo "$(date -u +%Y-%m-%dT%H-%M-%S)_${ns}"
}

maybe() { command -v "$1" >/dev/null 2>&1; }

git_info_json() {
  if maybe git && git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local commit dirty branch
    commit="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || true)"
    branch="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    dirty="false"
    if ! git -C "$PROJECT_ROOT" diff --quiet --ignore-submodules -- 2>/dev/null; then dirty="true"; fi
    if ! git -C "$PROJECT_ROOT" diff --cached --quiet --ignore-submodules -- 2>/dev/null; then dirty="true"; fi

    cat <<EOF
{"is_repo": true, "commit": "$(printf '%s' "$commit")", "branch": "$(printf '%s' "$branch")", "dirty": $dirty}
EOF
  else
    echo '{"is_repo": false}'
  fi
}

sha256_or_empty() {
  local f="$1"
  if [[ -f "$f" ]]; then
    if maybe sha256sum; then
      sha256sum "$f" | awk '{print $1}'
    elif maybe shasum; then
      shasum -a 256 "$f" | awk '{print $1}'
    else
      echo ""
    fi
  else
    echo ""
  fi
}

# Make a JSON array from a bash array (safe)
json_array_from_args() {
  "$PY" - <<'PY' "$@"
import json, sys
print(json.dumps(sys.argv[1:]))
PY
}

# ---- Session folder ----
SESSION_TS="$(utc_now_compact)"
SESSION_DIR="$DATA_ROOT/${PREFIX}_${SESSION_TS}"
mkdir -p "$SESSION_DIR"

echo "[collect.sh] Project root : $PROJECT_ROOT"
echo "[collect.sh] Using python : $PY"
echo "[collect.sh] TX script     : $TX_PY"
echo "[collect.sh] Data root     : $DATA_ROOT"
echo "[collect.sh] Session dir   : $SESSION_DIR"
echo "[collect.sh] Runs          : $RUNS"
echo "[collect.sh] tx.py args    : ${TX_ARGS[*]:-(none)}"

# Build JSON for tx args (fixes your bad substitution)
TX_ARGS_JSON="$(json_array_from_args "${TX_ARGS[@]}")"

# Write session.json (pass data via env; quoted heredoc prevents bash expansion)
GIT_JSON="$(git_info_json)"
TX_SHA="$(sha256_or_empty "$TX_PY")"
COLLECT_SHA="$(sha256_or_empty "$PROJECT_ROOT/collect.sh")"

export SESSION_ID
SESSION_ID="$(basename "$SESSION_DIR")"

export PROJECT_ROOT DATA_ROOT VENV_PY TX_PY TX_SHA COLLECT_SHA RUNS SLEEP_BETWEEN
export TX_ARGS_JSON GIT_JSON

VENV_PY="$PY"

"$PY" - <<'PY' > "$SESSION_DIR/session.json"
import json, os, platform, subprocess
from datetime import datetime, timezone

def cmd_out(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return ""

tx_args = json.loads(os.environ.get("TX_ARGS_JSON", "[]"))
git_info = json.loads(os.environ.get("GIT_JSON", '{"is_repo": false}'))

data = {
  "session_id": os.environ["SESSION_ID"],
  "created_utc": datetime.now(timezone.utc).isoformat(),
  "project_root": os.environ["PROJECT_ROOT"],
  "venv_python": os.environ["VENV_PY"],
  "tx_py": os.environ["TX_PY"],
  "tx_py_sha256": os.environ.get("TX_SHA",""),
  "collect_sh_sha256": os.environ.get("COLLECT_SHA",""),
  "data_root": os.environ["DATA_ROOT"],
  "runs_planned": int(os.environ["RUNS"]),
  "sleep_between_s": float(os.environ["SLEEP_BETWEEN"]),
  "tx_args": tx_args,
  "host": {
    "hostname": cmd_out(["hostname"]),
    "platform": platform.platform(),
    "uname": platform.uname()._asdict(),
    "python_version": platform.python_version(),
  },
  "git": git_info,
}
print(json.dumps(data, indent=2, sort_keys=True))
PY

# Index file for quick scan
echo "run_index,run_dir,exit_code,started_utc,ended_utc" > "$SESSION_DIR/index.csv"

# ---- Run loop ----
FAILS=0
for ((i=1; i<=RUNS; i++)); do
  RUN_ID="run_$(printf '%04d' "$i")"
  RUN_DIR="$SESSION_DIR/$RUN_ID"
  mkdir -p "$RUN_DIR"

  START_UTC="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  echo ""
  echo "[collect.sh] ===== $RUN_ID / $RUNS ====="
  echo "[collect.sh] Run dir: $RUN_DIR"
  echo "[collect.sh] Start  : $START_UTC"

  # Run from inside RUN_DIR so rx1.log/rx2.log land inside it (tx.py writes those by relative path)
  pushd "$RUN_DIR" >/dev/null

  set +e
  "$PY" "$TX_PY" --save-dir "$RUN_DIR" "${TX_ARGS[@]}" 2>&1 | tee "tx_stdout.log"
  TX_RC=${PIPESTATUS[0]}
  set -e

  popd >/dev/null
  END_UTC="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"

  # Collect list of capture files (if any)
  CAPTURES=()
  while IFS= read -r -d '' f; do CAPTURES+=("$(basename "$f")"); done < <(find "$RUN_DIR" -maxdepth 1 -type f -name "*_capture_*.iq" -print0 2>/dev/null || true)
  CAPTURES_JSON="$(json_array_from_args "${CAPTURES[@]}")"

  # Write run.json (again: pass JSON via env)
  export RUN_ID RUN_DIR START_UTC END_UTC TX_RC CAPTURES_JSON
  RUN_ID="$RUN_ID"
  RUN_DIR="$RUN_DIR"
  START_UTC="$START_UTC"
  END_UTC="$END_UTC"
  TX_RC="$TX_RC"

  "$PY" - <<'PY' > "$RUN_DIR/run.json"
import json, os, platform, subprocess

def cmd_out(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return ""

tx_args = json.loads(os.environ.get("TX_ARGS_JSON", "[]"))
captures = json.loads(os.environ.get("CAPTURES_JSON", "[]"))

data = {
  "run_id": os.environ["RUN_ID"],
  "session_id": os.environ["SESSION_ID"],
  "started_utc": os.environ["START_UTC"],
  "ended_utc": os.environ["END_UTC"],
  "exit_code": int(os.environ["TX_RC"]),
  "run_dir": os.environ["RUN_DIR"],
  "command": [os.environ["VENV_PY"], os.environ["TX_PY"], "--save-dir", os.environ["RUN_DIR"]] + tx_args,
  "captures": captures,
  "host": {
    "hostname": cmd_out(["hostname"]),
    "platform": platform.platform(),
    "python_version": platform.python_version(),
  },
}
print(json.dumps(data, indent=2, sort_keys=True))
PY

  echo "$i,$RUN_ID,$TX_RC,$START_UTC,$END_UTC" >> "$SESSION_DIR/index.csv"

  if [[ "$TX_RC" -ne 0 ]]; then
    echo "[collect.sh][WARN] $RUN_ID failed with exit code $TX_RC"
    FAILS=$((FAILS+1))
    if [[ "$FAIL_FAST" -eq 1 ]]; then
      echo "[collect.sh][ERROR] fail-fast enabled; stopping."
      break
    fi
  else
    echo "[collect.sh] $RUN_ID OK"
  fi

  if [[ "$(printf '%.6f' "$SLEEP_BETWEEN")" != "0.000000" ]]; then
    sleep "$SLEEP_BETWEEN"
  fi
done

echo ""
echo "[collect.sh] Done."
echo "[collect.sh] Session: $SESSION_DIR"
echo "[collect.sh] Failures: $FAILS"
echo "[collect.sh] Index: $SESSION_DIR/index.csv"
echo "[collect.sh] Session meta: $SESSION_DIR/session.json"
