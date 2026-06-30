#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_DIR="$ROOT_DIR/.visible-browser-profile"
SERVER_PORT=8765
REMOTE_DEBUGGING_PORT=9222
DRY_RUN=0

while (($# > 0)); do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

server_pids() {
  lsof -tiTCP:"$SERVER_PORT" -sTCP:LISTEN 2>/dev/null || true
}

chrome_pids() {
  pgrep -af -- "--remote-debugging-port=${REMOTE_DEBUGGING_PORT}" | awk -v profile="$PROFILE_DIR" '$0 ~ profile {print $1}'
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY RUN: scripts/stop.sh"
  echo "Would stop FastAPI listener on 127.0.0.1:${SERVER_PORT}"
  echo "Would stop Chrome debug processes matching --remote-debugging-port=${REMOTE_DEBUGGING_PORT} and profile ${PROFILE_DIR}"
  exit 0
fi

SERVER_PIDS="$(server_pids)"
if [[ -n "$SERVER_PIDS" ]]; then
  echo "$SERVER_PIDS" | xargs kill
  echo "Stopped FastAPI listener on port ${SERVER_PORT}: $SERVER_PIDS"
else
  echo "No FastAPI listener found on port ${SERVER_PORT}."
fi

CHROME_PIDS="$(chrome_pids)"
if [[ -n "$CHROME_PIDS" ]]; then
  echo "$CHROME_PIDS" | xargs kill
  echo "Stopped Chrome debug processes: $CHROME_PIDS"
else
  echo "No Chrome debug process found for profile ${PROFILE_DIR}."
fi
