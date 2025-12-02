#!/usr/bin/env bash
set -euo pipefail

# Location of this script (project root: NeuralNetworksProject)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Project root:          $SCRIPT_DIR"
echo


## Create VENV
chmod +x Codebase/Setup/create_venv.sh
"$SCRIPT_DIR/Codebase/Setup/create_venv.sh"
## Create Folders
chmod +x Codebase/Setup/make_folders.sh
"$SCRIPT_DIR/Codebase/Setup/make_folders.sh"

echo
echo "Setup complete."
echo "To activate the virtual environment, run:"
echo "  source \"$SCRIPT_DIR/.venv/bin/activate\""
