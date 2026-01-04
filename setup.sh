#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------
# setup.sh
# Linux/macOS equivalent of setup.bat
#
# Resolves PROJECT_ROOT as the folder this script lives in,
# then runs Codebase/Setup/setup_main.sh
# ---------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

MAIN="$PROJECT_ROOT/Codebase/Setup/setup_main.sh"

if [[ ! -f "$MAIN" ]]; then
  echo "ERROR: setup_main.sh not found at:"
  echo "  $MAIN"
  echo
  echo "Make sure you created Codebase/Setup/setup_main.sh (Linux conversion of setup.ps1)."
  exit 1
fi

echo "Running setup:"
echo "  $MAIN"
echo

# Run in a clean bash process; forward any args
bash "$MAIN" "$@"
EC=$?

echo
if [[ $EC -ne 0 ]]; then
  echo "Setup failed with exit code $EC."
  exit $EC
fi

# Match the Windows script's "pause" behavior only when interactive
if [[ -t 0 ]]; then
  read -r -p "Press Enter to close..." _
fi

exit 0
