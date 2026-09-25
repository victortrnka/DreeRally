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
#             after keys finish.
#   RUN_SECS  total seconds to let the game run before stopping it (default 12)
set -uo pipefail

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

log "starting Xvfb :99"
Xvfb :99 -screen 0 800x600x24 >>"$OUT_DIR/xvfb.log" 2>&1 &
XVFB_PID=$!
for i in $(seq 1 50); do
	xdpyinfo -display :99 >/dev/null 2>&1 && break
	sleep 0.1
done
if ! xdpyinfo -display :99 >/dev/null 2>&1; then
	log "Xvfb failed to come up"
	echo "xvfb-failed" > "$OUT_DIR/status.txt"
	exit 2
fi

log "wineboot --init (WINEPREFIX=$WINEPREFIX)"
timeout 60 wineboot --init >>"$LOG" 2>&1
timeout 30 wineserver -w >>"$LOG" 2>&1 || true

# Print a text backtrace on crash instead of popping up a GUI dialog
# (there is no one to click it in a headless container).
wine reg add "HKCU\\Software\\Wine\\WineDbg" /v ShowCrashDialog /t REG_DWORD /d 0 /f >>"$LOG" 2>&1
timeout 15 wineserver -w >>"$LOG" 2>&1 || true

log "wine --version: $(wine --version)"

cd "$RUNTIME_DIR"
DR_ARGS="${DR_ARGS:--window -nosound}"
RUN_SECS="${RUN_SECS:-12}"
log "launching: wine dreerally.exe $DR_ARGS"
T0=$(date +%s)
wine dreerally.exe $DR_ARGS >>"$LOG" 2>&1 &
GAME_PID=$!

shoot() {
	local label="$1"
	if xwd -root -display :99 -out "$OUT_DIR/${label}.xwd" 2>>"$LOG"; then
		convert "$OUT_DIR/${label}.xwd" "$OUT_DIR/${label}.png" 2>>"$LOG"
		rm -f "$OUT_DIR/${label}.xwd"
		log "screenshot ${label} at $(( $(date +%s) - T0 ))s"
	else
		log "screenshot ${label} FAILED"
	fi
}

for spec in ${DR_SHOTS:-3:intro 9:menu}; do
	t="${spec%%:*}"
	label="${spec##*:}"
	while [ $(( $(date +%s) - T0 )) -lt "$t" ]; do
		if ! kill -0 "$GAME_PID" 2>/dev/null; then
			log "game exited before shot ${label} (t=${t}s)"
			break 2
		fi
		sleep 0.2
	done
	shoot "$label"
done

if [ -n "${DR_KEYS:-}" ] && kill -0 "$GAME_PID" 2>/dev/null; then
	log "running keys.exe $DR_KEYS"
	wine "$RUNTIME_DIR/keys.exe" $DR_KEYS >>"$OUT_DIR/keys.log" 2>&1
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
	wait "$GAME_PID" 2>/dev/null
else
	wait "$GAME_PID" 2>/dev/null
	RC=$?
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
if [ "$STATUS" = "crashed" ]; then
	command grep -a -A 30 "Unhandled" "$LOG" > "$OUT_DIR/crash.txt" || true
	exit 1
fi
exit 0
