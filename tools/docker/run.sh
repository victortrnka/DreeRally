#!/usr/bin/env bash
# Host-side launcher for the headless Docker test runner.
#
# Usage:
#   RUNTIME_DIR=/path/to/runtime OUT_DIR=/path/to/out tools/docker/run.sh \
#       [DR_ARGS="-window -nosound"] [DR_SHOTS="3:intro 9:menu"] [DR_KEYS="down enter"]
#
# RUNTIME_DIR must hold dreerally.exe, the RUNTIME_FILES assets (see the
# top-level Makefile), and optionally keys.exe. It is mounted read-write so
# Wine/the game can write dr.cfg and its own WINEPREFIX-relative state.
# OUT_DIR receives wine.log, status.txt, and any screenshots as PNG.
set -euo pipefail

IMAGE="dreerally-wine:trial"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${RUNTIME_DIR:?set RUNTIME_DIR to the host dir with dreerally.exe + game files}"
: "${OUT_DIR:?set OUT_DIR to the host dir for logs/screenshots}"
RUNTIME_DIR="$(cd "$RUNTIME_DIR" && pwd)"
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
	echo "Building $IMAGE ..." >&2
	docker build --platform linux/amd64 -t "$IMAGE" "$SCRIPT_DIR"
fi

NAME="${NAME:-dreerally-trial-$$}"
RUN_SECS="${RUN_SECS:-12}"
# Host-side bound in case the container itself wedges (e.g. a wineserver
# hang not caught by entrypoint.sh's own internal timeouts): RUN_SECS plus
# generous headroom for boot + screenshots + keys.exe. No `timeout`/
# `gtimeout` binary is assumed on the host, so this is a plain bash
# background-and-poll loop instead.
HOST_BOUND=$((RUN_SECS + 120))

set +e
docker run --rm --platform linux/amd64 --name "$NAME" \
	-v "$RUNTIME_DIR:/runtime" \
	-v "$OUT_DIR:/out" \
	-e DR_ARGS="${DR_ARGS:--window -nosound}" \
	-e DR_SHOTS="${DR_SHOTS:-3:intro 9:menu}" \
	-e DR_KEYS="${DR_KEYS:-}" \
	-e RUN_SECS="$RUN_SECS" \
	-e AUDIO="${AUDIO:-0}" \
	"$IMAGE" &
DOCKER_PID=$!

ELAPSED=0
while kill -0 "$DOCKER_PID" 2>/dev/null; do
	if [ "$ELAPSED" -ge "$HOST_BOUND" ]; then
		echo "run.sh: container $NAME exceeded ${HOST_BOUND}s host-side bound, killing it" >&2
		docker kill "$NAME" >/dev/null 2>&1
		break
	fi
	sleep 1
	ELAPSED=$((ELAPSED + 1))
done
wait "$DOCKER_PID"
STATUS_RC=$?
set -e

if [ -f "$OUT_DIR/status.txt" ]; then
	echo "status: $(cat "$OUT_DIR/status.txt")"
elif [ "$ELAPSED" -ge "$HOST_BOUND" ]; then
	echo "status: host-timeout"
fi
exit $STATUS_RC
