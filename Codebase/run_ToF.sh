#!/usr/bin/env bash
set -euo pipefail

# cd to project root (folder containing Codebase/)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$HERE/Codebase" ]]; then
  cd "$HERE"
else
  cd "$HERE/.."
fi

# Pick python: prefer project venv, fall back to system python3
PY="./.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "WARN: Couldn't find venv python at $PY"
  if command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
    echo "Using system python: $PY"
  else
    echo "ERROR: python3 not found and venv missing at ./.venv/bin/python"
    exit 1
  fi
fi


#read -r -p "Enter the directory to process: " DIR
#if [[ ! -d "$DIR" ]]; then
#  echo "ERROR: Folder not found: $DIR"
#  exit 1
#fi


"$PY" -m Codebase.UugaDuuga

#--root "$DIR"

echo "All scripts completed successfully."