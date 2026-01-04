#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------
# Codebase/Setup/setup_main.sh
# Linux/macOS equivalent of Codebase/Setup/setup.ps1
#
# - Finds project root
# - Runs create_venv.py with system python
# - Runs make_folders.py + setup_config.py with venv python if available
#   (fallbacks to system python)
# ---------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

CREATE_VENV="$SCRIPT_DIR/create_venv.py"
MAKE_FOLDERS="$SCRIPT_DIR/make_folders.py"
SETUP_CONFIG="$SCRIPT_DIR/setup_config.py"

assert_file_exists() {
  local path="$1" name="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: $name not found at: $path" >&2
    exit 1
  fi
}

get_system_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"; return 0
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"; return 0
  fi
  return 1
}

assert_file_exists "$CREATE_VENV"  "create_venv.py"
assert_file_exists "$MAKE_FOLDERS" "make_folders.py"
assert_file_exists "$SETUP_CONFIG" "setup_config.py"

SYS_PY="$(get_system_python || true)"
if [[ -z "$SYS_PY" ]]; then
  echo "ERROR: Python not found. Install Python 3 and ensure 'python3' (or 'python') is on PATH." >&2
  exit 1
fi

echo "Project root: $PROJECT_ROOT"

# Ensure consistent working directory (many projects assume root)
cd "$PROJECT_ROOT"

echo "Running: create_venv.py"
"$SYS_PY" "$CREATE_VENV"

# Common venv location created by create_venv.py
VENV_PY="$PROJECT_ROOT/.venv/bin/python"

if [[ -x "$VENV_PY" ]]; then
  echo "Using venv python: $VENV_PY"

  echo "Running: make_folders.py"
  "$VENV_PY" "$MAKE_FOLDERS"

  echo "Running: setup_config.py"
  "$VENV_PY" "$SETUP_CONFIG"
else
  echo "Venv python not found/executable at: $VENV_PY"
  echo "Falling back to system python for: make_folders.py + setup_config.py"

  "$SYS_PY" "$MAKE_FOLDERS"
  "$SYS_PY" "$SETUP_CONFIG"
fi

echo "Setup complete."
