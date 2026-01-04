#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------
# collect.sh
# Runs Codebase/Collection/tx.py using the project's .venv
# ---------------------------------------

# Resolve PROJECT_ROOT as the directory containing this script
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

VENV_DIR="$PROJECT_ROOT/.venv"
TX_PY="$PROJECT_ROOT/Codebase/Collection/tx.py"

# ---- Validate paths ----
if [[ ! -d "$VENV_DIR" ]]; then
  echo "[ERROR] .venv not found at: $VENV_DIR" >&2
  echo "        Create it first (example): python3 -m venv .venv" >&2
  exit 1
fi

if [[ ! -f "$TX_PY" ]]; then
  echo "[ERROR] tx.py not found at: $TX_PY" >&2
  exit 1
fi

# ---- Activate venv ----
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# Prefer the venv python explicitly (more robust than relying on activation alone)
PY="$VENV_DIR/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "[ERROR] venv python not executable: $PY" >&2
  exit 1
fi

# ---- Run ----
echo "[collect.sh] Project root : $PROJECT_ROOT"
echo "[collect.sh] Using python : $PY"
echo "[collect.sh] Running      : $TX_PY $*"

exec "$PY" "$TX_PY" "$@"
