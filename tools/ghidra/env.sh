# Shared settings for the Ghidra helper scripts (sourced, not executed).
: "${GHIDRA_HOME:=$(ls -d /opt/homebrew/Caskroom/ghidra/*/ghidra_*_PUBLIC 2>/dev/null | tail -1)}"
if [ -z "$GHIDRA_HOME" ]; then
  # Homebrew now ships Ghidra as a core formula (no more --cask ghidra).
  # brew --prefix can fail (no brew, or ghidra not installed via brew); keep
  # that non-fatal so the "Ghidra not found" check below fails loudly
  # instead of this script silently aborting on `set -e`.
  brew_ghidra=$(brew --prefix ghidra 2>/dev/null) || brew_ghidra=""
  if [ -n "$brew_ghidra" ]; then
    GHIDRA_HOME="$brew_ghidra/libexec"
  fi
fi
: "${JAVA_HOME:=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home}"
export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
GHIDRA_HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"
GHIDRA_PROJECT_DIR="${GHIDRA_PROJECT_DIR:-$HOME/Ghidra/DreeRally}"
GHIDRA_PROJECT=DreeRally
GHIDRA_LOG="${TMPDIR:-/tmp}/dreerally-ghidra.log"
DR_EXE_SHA256=54fe789faca583d67b8e73e7c58908f3f1468c5c8f75942239a60483ae9be58c
if [ ! -x "$GHIDRA_HEADLESS" ]; then
  echo "Ghidra not found (GHIDRA_HOME=$GHIDRA_HOME); see doc/DEVELOPMENT.md" >&2
  exit 1
fi

# Runs analyzeHeadless with the given arguments; on failure shows the log tail.
run_headless() {
  if ! "$GHIDRA_HEADLESS" "$GHIDRA_PROJECT_DIR" "$GHIDRA_PROJECT" "$@" > "$GHIDRA_LOG" 2>&1; then
    echo "Ghidra headless failed (is the project open in the Ghidra GUI?). Log tail:" >&2
    tail -20 "$GHIDRA_LOG" >&2
    exit 1
  fi
}
