#!/bin/bash
# Runs inside the container. Starts Xvfb, inits a fresh WINEPREFIX, launches
# dreerally.exe, takes screenshots at requested offsets, optionally drives
# input via keys.exe, then reports a clear status.
#
# Env vars (all optional):
#   DR_ARGS   extra dreerally.exe args, e.g. "-window -nosound -nogl"
#   DR_SHOTS  space-separated "seconds:label" pairs, e.g. "3:intro 8:menu"
#   DR_KEYS   tokens passed to keys.exe, e.g. "down down enter", run after
#             the last screenshot in DR_SHOTS. A "shot:<label>" token splits
#             the sequence there: the keys before it run first, a screenshot
#             <label>.png is taken, then the next segment runs. A final
#             "after_keys" screenshot is always taken once every segment has
#             run. Each keys.exe invocation is bounded by the time left until
#             RUN_SECS+30s after game launch (keys.exe itself waits up to
#             ~60s for the game window before giving up), so a hang in any
#             one segment cannot outlive the overall bound.
#   RUN_SECS  total seconds to let the game run before stopping it (default 12)
#   AUDIO     1 = start PulseAudio with a null sink and record its monitor
#             to audio.wav in OUT_DIR for the whole run (opt-in: off by
#             default, since it costs a PulseAudio daemon + a parec process
#             most runs don't need). Requires DR_ARGS without -nosound.
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

AUDIO="${AUDIO:-0}"
PAREC_PID=""
if [ "$AUDIO" = "1" ]; then
	export XDG_RUNTIME_DIR=/tmp/xdg-runtime
	mkdir -p "$XDG_RUNTIME_DIR"
	log "starting PulseAudio (null sink) for audio capture"
	if ! PULSE_SERVER= pulseaudio -D --exit-idle-time=-1 --disallow-exit >>"$OUT_DIR/pulse.log" 2>&1; then
		fail_setup "pulseaudio failed to start"
	fi
	PULSE_UP=0
	for i in $(seq 1 50); do
		if pactl info >>"$OUT_DIR/pulse.log" 2>&1; then
			PULSE_UP=1
			break
		fi
		sleep 0.1
	done
	[ "$PULSE_UP" -eq 1 ] || fail_setup "pulseaudio did not come up"
	pactl load-module module-null-sink sink_name=drsink sink_properties=device.description=drsink >>"$OUT_DIR/pulse.log" 2>&1 \
		|| fail_setup "module-null-sink failed to load"
	pactl set-default-sink drsink >>"$OUT_DIR/pulse.log" 2>&1 || true
	parec --device=drsink.monitor --file-format=wav "$OUT_DIR/audio.wav" >>"$OUT_DIR/pulse.log" 2>&1 &
	PAREC_PID=$!
	log "recording drsink.monitor to audio.wav (parec pid $PAREC_PID)"
fi

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
	# Bound derived from RUN_SECS rather than a fixed constant, so a longer
	# scenario (e.g. a full race) gets a proportionally longer bound while a
	# short one still fails fast. KEYS_DEADLINE is a fixed point in time, and
	# every segment's timeout is however much of it is left, so N segments
	# can never together run longer than a single bound would have.
	KEYS_BOUND_SECS=$((RUN_SECS + 30))
	KEYS_DEADLINE=$((T0 + KEYS_BOUND_SECS))
	log "running keys.exe from DR_KEYS (bound: RUN_SECS+30=${KEYS_BOUND_SECS}s from launch)"

	run_keys_segment() {
		local seg="$1"
		if [ -z "$seg" ]; then
			return 0
		fi
		local remaining=$((KEYS_DEADLINE - $(date +%s)))
		if [ "$remaining" -le 0 ]; then
			log "keys.exe segment skipped: ${KEYS_BOUND_SECS}s bound already used up"
			KEYS_TIMEOUT=1
			return 0
		fi
		if ! timeout "$remaining" wine "$RUNTIME_DIR/keys.exe" $seg >>"$OUT_DIR/keys.log" 2>&1; then
			log "keys.exe segment timed out or failed (had ${remaining}s left): $seg"
			KEYS_TIMEOUT=1
		fi
	}

	SEG=""
	for tok in $DR_KEYS; do
		case "$tok" in
			shot:*)
				run_keys_segment "$SEG"
				SEG=""
				shoot "${tok#shot:}"
				;;
			*)
				SEG="${SEG:+$SEG }$tok"
				;;
		esac
	done
	run_keys_segment "$SEG"
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

if [ -n "$PAREC_PID" ]; then
	# SIGTERM (not -9) so parec finalizes the WAV header before exiting.
	kill "$PAREC_PID" 2>/dev/null || true
	wait "$PAREC_PID" 2>/dev/null || true
	log "audio capture stopped ($(du -h "$OUT_DIR/audio.wav" 2>/dev/null | cut -f1 || echo '?'))"
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
