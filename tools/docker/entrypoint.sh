#!/bin/bash
# Runs inside the container. Starts Xvfb, inits a fresh WINEPREFIX, launches
# dreerally.exe, takes screenshots at requested offsets, optionally drives
# input via keys.exe, then reports a clear status.
#
# Env vars (all optional):
#   DR_ARGS   extra dreerally.exe args, e.g. "-window -nosound -gl"
#   DR_SHOTS  space-separated "seconds:label" pairs, e.g. "3:intro 8:menu"
#   DR_KEYS   tokens passed to keys.exe, e.g. "down down enter", run after
#             the last screenshot in DR_SHOTS; a final screenshot is taken
#             after keys finish. Bounded by a 90s timeout (keys.exe itself
#             waits up to ~60s for the game window before giving up).
#   RUN_SECS  total seconds to let the game run before stopping it (default 12)
#
# Exit code / STATUS: 0 only for STATUS=alive or STATUS=exited(rc=0). Every
# other STATUS (crashed, exited(rc=N) with N!=0, setup-failed, xvfb-failed,
# keys-timeout) exits non-zero, so a caller can rely on $? alone.
set -euo pipefail

export DISPLAY=:99
export WINEARCH=win32
export WINEPREFIX=/wineprefix
export WINEDEBUG=fixme-all
# No real GPU in the container; force Mesa's software rasterizer for GL mode.
export LIBGL_ALWAYS_SOFTWARE=1

RUNTIME_DIR=/runtime
OUT_DIR=/out
LOG="$OUT_DIR/wine.log"
mkdir -p "$OUT_DIR"
: > "$LOG"

log() { echo "[entrypoint] $*" | tee -a "$LOG"; }

# Single place to bail out before the game is even launched: log why, write
# status.txt, clean up what's running, exit non-zero.
fail_setup() {
	log "SETUP FAILED: $*"
	echo "setup-failed" > "$OUT_DIR/status.txt"
	[ -n "${XVFB_PID:-}" ] && kill -9 "$XVFB_PID" 2>/dev/null || true
	exit 3
}

log "starting Xvfb :99"
Xvfb :99 -screen 0 800x600x24 >>"$OUT_DIR/xvfb.log" 2>&1 &
XVFB_PID=$!
XVFB_UP=0
for i in $(seq 1 50); do
	if xdpyinfo -display :99 >/dev/null 2>&1; then
		XVFB_UP=1
		break
	fi
	sleep 0.1
done
if [ "$XVFB_UP" -ne 1 ]; then
	log "Xvfb failed to come up"
	echo "xvfb-failed" > "$OUT_DIR/status.txt"
	kill -9 "$XVFB_PID" 2>/dev/null || true
	exit 2
fi

log "wineboot --init (WINEPREFIX=$WINEPREFIX)"
if ! timeout 60 wineboot --init >>"$LOG" 2>&1; then
	fail_setup "wineboot --init failed or timed out"
fi
timeout 30 wineserver -w >>"$LOG" 2>&1 || true

# Print a text backtrace on crash instead of popping up a GUI dialog
# (there is no one to click it in a headless container).
timeout 15 wine reg add "HKCU\\Software\\Wine\\WineDbg" /v ShowCrashDialog /t REG_DWORD /d 0 /f >>"$LOG" 2>&1 || true
timeout 15 wineserver -w >>"$LOG" 2>&1 || true

log "wine --version: $(wine --version)"

if ! cd "$RUNTIME_DIR"; then
	fail_setup "cd $RUNTIME_DIR failed (bad mount?)"
fi
DR_ARGS="${DR_ARGS:--window -nosound}"
RUN_SECS="${RUN_SECS:-12}"
log "launching: wine dreerally.exe $DR_ARGS"
T0=$(date +%s)
wine dreerally.exe $DR_ARGS >>"$LOG" 2>&1 &
GAME_PID=$!

shoot() {
	local label="$1"
	if xwd -root -display :99 -out "$OUT_DIR/${label}.xwd" 2>>"$LOG"; then
		convert "$OUT_DIR/${label}.xwd" "$OUT_DIR/${label}.png" 2>>"$LOG" || true
		rm -f "$OUT_DIR/${label}.xwd"
		log "screenshot ${label} at $(( $(date +%s) - T0 ))s"
	else
		log "screenshot ${label} FAILED"
	fi
}

GAME_EXITED_EARLY=0
for spec in ${DR_SHOTS:-3:intro 9:menu}; do
	t="${spec%%:*}"
	label="${spec##*:}"
	while [ $(( $(date +%s) - T0 )) -lt "$t" ]; do
		if ! kill -0 "$GAME_PID" 2>/dev/null; then
			log "game exited before shot ${label} (t=${t}s)"
			GAME_EXITED_EARLY=1
			break
		fi
		sleep 0.2
	done
	[ "$GAME_EXITED_EARLY" -eq 1 ] && break
	shoot "$label"
done

KEYS_TIMEOUT=0
if [ -n "${DR_KEYS:-}" ] && [ "$GAME_EXITED_EARLY" -eq 0 ] && kill -0 "$GAME_PID" 2>/dev/null; then
	log "running keys.exe $DR_KEYS (90s bound)"
	if ! timeout 90 wine "$RUNTIME_DIR/keys.exe" $DR_KEYS >>"$OUT_DIR/keys.log" 2>&1; then
		log "keys.exe timed out or failed"
		KEYS_TIMEOUT=1
	fi
	shoot "after_keys"
fi

while [ $(( $(date +%s) - T0 )) -lt "$RUN_SECS" ]; do
	kill -0 "$GAME_PID" 2>/dev/null || break
	sleep 0.5
done

if kill -0 "$GAME_PID" 2>/dev/null; then
	STATUS="alive"
	kill -9 "$GAME_PID" 2>/dev/null || true
	for i in $(seq 1 25); do
		kill -0 "$GAME_PID" 2>/dev/null || break
		sleep 0.2
	done
	wait "$GAME_PID" 2>/dev/null || true
else
	RC=0
	wait "$GAME_PID" 2>/dev/null || RC=$?
	# Give a crashed process's winedbg backtrace time to finish and flush.
	timeout 15 wineserver -w >>"$LOG" 2>&1 || true
	if command grep -a -q "Unhandled" "$LOG"; then
		STATUS="crashed"
	else
		STATUS="exited(rc=$RC)"
	fi
fi

timeout 15 wineserver -k >>"$LOG" 2>&1 || true
kill -9 "$XVFB_PID" 2>/dev/null || true

log "STATUS=$STATUS"
echo "$STATUS" > "$OUT_DIR/status.txt"

EXIT_CODE=0
case "$STATUS" in
	alive) EXIT_CODE=0 ;;
	exited\(rc=0\)) EXIT_CODE=0 ;;
	crashed)
		EXIT_CODE=1
		command grep -a -A 30 "Unhandled" "$LOG" > "$OUT_DIR/crash.txt" || true
		;;
	*) EXIT_CODE=1 ;;  # exited(rc=N) with N != 0
esac
if [ "$KEYS_TIMEOUT" -eq 1 ] && [ "$EXIT_CODE" -eq 0 ]; then
	log "forcing non-zero exit: keys.exe timed out even though the game itself looked fine"
	EXIT_CODE=1
fi
exit "$EXIT_CODE"
