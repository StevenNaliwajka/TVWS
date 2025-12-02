#!/usr/bin/env bash
set -euo pipefail

# Location of this script (Codebase/Setup)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Project root: go up two levels from Codebase/Setup → NeuralNetworksProject
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Virtual environment directory
VENV_DIR="$PROJECT_ROOT/.venv"

# JSON requirements file
REQ_JSON="$SCRIPT_DIR/requirements.json"

echo "Script dir:      $SCRIPT_DIR"
echo "Project root:    $PROJECT_ROOT"
echo "Virtualenv dir:  $VENV_DIR"
echo "Requirements:    $REQ_JSON"
echo

# Sanity checks
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is not installed or not in PATH."
    exit 1
fi

if [ ! -f "$REQ_JSON" ]; then
    echo "ERROR: requirements.json not found at: $REQ_JSON"
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists, reusing it."
fi

# Activate venv
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip

echo "Parsing requirements.json..."
# Read package list from JSON with Python
PKGS=$(REQ_JSON="$REQ_JSON" python3 << 'PY'
import json, os, sys

path = os.environ["REQ_JSON"]
with open(path, "r") as f:
    data = json.load(f)

# Accept either:
# 1) ["pkg1==1.0", "pkg2>=2.0"]
# 2) {"packages": ["pkg1==1.0", "pkg2>=2.0"]}
if isinstance(data, dict):
    pkgs = data.get("packages", [])
else:
    pkgs = data

if not isinstance(pkgs, list):
    print("ERROR: requirements.json must be a list or have a 'packages' list.", file=sys.stderr)
    sys.exit(1)

# Print one per line for Bash word-splitting
print("\n".join(str(p) for p in pkgs))
PY
)

if [ -z "$PKGS" ]; then
    echo "No packages found in requirements.json; skipping pip install."
else
    echo "Installing packages:"
    printf '  %s\n' $PKGS
    pip install $PKGS
fi

echo
echo "Done! To use the environment later, run:"
echo "  source \"$VENV_DIR/bin/activate\""
