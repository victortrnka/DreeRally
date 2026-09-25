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

# A build interrupted mid-link (e.g. the laptop sleeping) can leave a
# half-written *.partial.* directory behind; it is never a valid cache.
rm -rf "$repo"/build/equiv/*.partial.* 2>/dev/null || true

if [ ! -f "$cache/dreerally.exe" ] || [ ! -f "$cache/dreerally.map" ]; then
  wt=$(mktemp -d "${TMPDIR:-/tmp}/dreerally-equiv.XXXXXX")
  partial="$cache.partial.$$"
  trap 'rm -rf "$partial"; git -C "$repo" worktree remove --force "$wt" >/dev/null 2>&1 || true' EXIT
  git worktree add --detach --quiet "$wt" "$base_sha"
  # Old commits may predate the Makefile: always build them with the current one.
  cp Makefile "$wt/Makefile"
  rm -rf "$partial"
  make -C "$wt" --no-print-directory -s PROFILE=equiv OUT="$partial" all
  # Only now is the base build known-complete: move it into place atomically
  # so a crash after this point can never leave a partial cache directory.
  if [ ! -f "$partial/dreerally.exe" ] || [ ! -f "$partial/dreerally.map" ]; then
    echo "check-equiv: base build did not produce dreerally.exe and dreerally.map" >&2
    exit 1
  fi
  rm -rf "$cache"
  mv "$partial" "$cache"
fi

# The working tree is always rebuilt from scratch, so no stale object can hide a change.
rm -rf "$work"
make --no-print-directory -s PROFILE=equiv OUT="$work" all

python3 tools/equiv/equiv.py "$cache/dreerally.exe" "$work/dreerally.exe"
