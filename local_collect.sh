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

# Only sudo if not already root
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  exec sudo -E "$PY" "$PROJECT_ROOT/Codebase/Collection/Local/local_collect.py" "$@"
else
  exec "$PY" "$PROJECT_ROOT/Codebase/Collection/Local/local_collect.py" "$@"
fi
