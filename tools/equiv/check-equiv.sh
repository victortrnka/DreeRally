#!/bin/bash
# Proves that the working tree compiles to the same machine code as BASE.
# Usage: tools/equiv/check-equiv.sh [BASE]    (default: HEAD)
set -euo pipefail

base_rev=${1:-HEAD}
repo=$(git rev-parse --show-toplevel)
cd "$repo"
base_sha=$(git rev-parse --verify "$base_rev^{commit}")
# The flags live in the Makefile, so a Makefile change invalidates cached base builds.
mk_hash=$(shasum -a 256 Makefile | cut -c1-12)
cache="$repo/build/equiv/$base_sha-$mk_hash"
work="$repo/build/equiv/worktree"

if [ ! -f "$cache/dreerally.exe" ]; then
  wt=$(mktemp -d "${TMPDIR:-/tmp}/dreerally-equiv.XXXXXX")
  trap 'git -C "$repo" worktree remove --force "$wt" >/dev/null 2>&1 || true' EXIT
  git worktree add --detach --quiet "$wt" "$base_sha"
  # Old commits may predate the Makefile: always build them with the current one.
  cp Makefile "$wt/Makefile"
  rm -rf "$cache"
  make -C "$wt" --no-print-directory -s PROFILE=equiv OUT="$cache" all
fi

# The working tree is always rebuilt from scratch, so no stale object can hide a change.
rm -rf "$work"
make --no-print-directory -s PROFILE=equiv OUT="$work" all

python3 tools/equiv/equiv.py "$cache/dreerally.exe" "$work/dreerally.exe"
