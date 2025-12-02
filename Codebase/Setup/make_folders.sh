#!/usr/bin/env bash
set -euo pipefail

# Figure out PROJECT_ROOT based on this script's location:
# .../NeuralNetworksProject/Codebase/Setup/make_folders.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

## DIR locations
DATA_DIR="$PROJECT_ROOT/Data"
CONFIG_DIR="$PROJECT_ROOT/Config"

create_dir_if_missing() {
    local dir_path="$1"
    local name="$2"

    if [ ! -d "$dir_path" ]; then
        echo "Creating $name folder at: $dir_path"
        mkdir -p "$dir_path"
    else
        echo "$name folder already exists at: $dir_path, reusing it."
    fi
}

create_dir_if_missing "$DATA_DIR"   "Data"
create_dir_if_missing "$CONFIG_DIR" "Config"
