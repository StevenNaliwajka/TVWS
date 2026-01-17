#!/usr/bin/env bash
set -euo pipefail

# Project root is the directory containing this script.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="$PROJECT_ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

echo "[local_collect.sh] Project root: $PROJECT_ROOT"
echo "[local_collect.sh] Python      : $PY"
echo "[local_collect.sh] Mode        : python -m Codebase.Collection.Local.local_collect"

cd "$PROJECT_ROOT"
exec "$PY" -m Codebase.Collection.Local.local_collect
