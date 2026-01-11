#!/usr/bin/env bash
set -euo pipefail

# Project root is the directory containing this script.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="$PROJECT_ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

SCRIPT="$PROJECT_ROOT/Codebase/Collection/Local/local_collect.py"

echo "[local_collect.sh] Project root: $PROJECT_ROOT"
echo "[local_collect.sh] Python      : $PY"
echo "[local_collect.sh] Script      : $SCRIPT"

exec "$PY" "$SCRIPT"
