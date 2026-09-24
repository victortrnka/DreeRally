#!/bin/bash
# Creates the Ghidra project with the original dr.exe and runs auto-analysis once.
# Usage: tools/ghidra/setup.sh [path/to/dr.exe]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/env.sh"
default_exe="$HOME/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Death Rally/Death Rally/dr.exe"
exe=${1:-$default_exe}
actual=$(shasum -a 256 "$exe" | cut -d' ' -f1)
if [ "$actual" != "$DR_EXE_SHA256" ]; then
  echo "Unexpected dr.exe ($actual); the decompilation matches $DR_EXE_SHA256 only" >&2
  exit 1
fi
mkdir -p "$GHIDRA_PROJECT_DIR"
run_headless -import "$exe" -overwrite
echo "Ghidra project ready: $GHIDRA_PROJECT_DIR/$GHIDRA_PROJECT"
