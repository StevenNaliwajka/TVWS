#!/usr/bin/env bash
set -euo pipefail

# Resolve project root (directory where this script lives)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
#SCRIPT="$PROJECT_ROOT/Codebase/Collection/Waveform/make_square_iq.py"
SCRIPT="$PROJECT_ROOT/Codebase/UugaDuuga.py"

# Ensure venv exists
if [[ ! -d "$VENV_DIR" ]]; then
  echo "[ERROR] Virtual environment not found at: $VENV_DIR"
  echo "        Create it with:"
  echo "        python3 -m venv .venv"
  exit 1
fi

# Ensure run.py exists
if [[ ! -f "$SCRIPT" ]]; then
  echo "[ERROR] Script not found: $SCRIPT"
  exit 1
fi

# Activate venv
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# Make project root importable as a package root (so `import Codebase` works)
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# Run the script unbuffered; merge stderr into stdout so all messages appear
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
exec "$PYTHON_BIN" -u "$SCRIPT" "$@" 2>&1
