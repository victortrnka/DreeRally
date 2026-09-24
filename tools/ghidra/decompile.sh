#!/bin/bash
# Prints Ghidra's decompilation of the original function containing an address.
# Usage: tools/ghidra/decompile.sh 0x415710
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
source "$here/env.sh"
addr=${1:?usage: decompile.sh <address, e.g. 0x415710>}
out=$(mktemp)
rm -f "$out"
run_headless -process dr.exe -noanalysis -readOnly -scriptPath "$here" -postScript DecompileAt.java "$addr" "$out"
if [ ! -s "$out" ]; then
  grep 'DecompileAt.java>' "$GHIDRA_LOG" | sed 's/.*DecompileAt.java> //' >&2
  exit 1
fi
cat "$out"
