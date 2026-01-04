#!/usr/bin/env bash
set -euo pipefail

# --- Go to project root (folder containing Codebase/) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/Codebase" ]]; then
  cd "$SCRIPT_DIR"
elif [[ -d "$SCRIPT_DIR/../Codebase" ]]; then
  cd "$SCRIPT_DIR/.."
else
  echo "ERROR: Couldn't locate project root (no Codebase/ found)."
  exit 1
fi

# --- Pick python interpreter from venv (matches PyCharm) ---
PY="./.venv/Scripts/python.exe"
if [[ ! -f "$PY" ]]; then
  echo "ERROR: Couldn't find venv python at: $PY"
  echo "If your venv folder name is different, update PY in this script."
  exit 1
fi

# --- Ask user for the data/results directory ---
read -r -p "Enter the directory to process: " ROOT_DIR
if [[ ! -d "$ROOT_DIR" ]]; then
  echo "ERROR: Folder not found: $ROOT_DIR"
  exit 1
fi

# --- Run the three scripts in order (as modules so Codebase imports work) ---
"$PY" -m Codebase.UugaDuuga --root "$ROOT_DIR"
"$PY" -m Codebase.ToFSheetAverage --root "$ROOT_DIR"
"$PY" -m Codebase.ToFSheetAverageAdd --root "$ROOT_DIR"

echo "All scripts completed successfully."
