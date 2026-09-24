#!/bin/bash
# Applies our function names (from the //----- (ADDR) markers) to the Ghidra project.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/env.sh"
tsv=$(mktemp)
python3 "$here/collect_names.py" > "$tsv"
run_headless -process dr.exe -noanalysis -scriptPath "$here" -postScript SyncNames.java "$tsv"
grep 'SyncNames.java>' "$GHIDRA_LOG" | sed 's/.*SyncNames.java> //' || true
grep -q 'SyncNames.java> SUMMARY' "$GHIDRA_LOG" || { echo "SyncNames did not finish; see $GHIDRA_LOG" >&2; exit 1; }
