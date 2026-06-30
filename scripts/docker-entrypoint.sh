#!/usr/bin/env bash
set -euo pipefail

CHROME_PROFILE="${CHROME_PROFILE:-/home/ds160/chrome-profile}"
CDP_PORT="${CDP_PORT:-9222}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8765}"
CEAC_URL="${CEAC_URL:-https://ceac.state.gov/genniv/}"
HEADLESS="${HEADLESS:-new}"  # set HEADLESS=0 for visible mode with VNC

echo "==> Starting Chromium (CDP on port ${CDP_PORT}, headless=${HEADLESS})..."
# Build chrome flags
CHROME_FLAGS=(
    --no-sandbox
    --disable-gpu
    --disable-dev-shm-usage
    --disable-software-rasterizer
    --disable-background-networking
    --disable-sync
    --no-first-run
    --no-default-browser-check
    --remote-debugging-port="${CDP_PORT}"
    --remote-debugging-address=0.0.0.0
    --user-data-dir="${CHROME_PROFILE}"
    --window-size=1920,1080
)
if [[ "${HEADLESS}" != "0" ]]; then
    CHROME_FLAGS+=(--headless="${HEADLESS}")
fi

chromium "${CHROME_FLAGS[@]}" "${CEAC_URL}" &
CHROME_PID=$!

# Wait for CDP to become ready
echo "==> Waiting for CDP on port ${CDP_PORT}..."
for i in $(seq 1 30); do
    if curl -s "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
        echo "==> CDP ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: CDP did not become ready in 30s" >&2
        kill "${CHROME_PID}" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

cleanup() {
    echo "==> Shutting down..."
    kill "${CHROME_PID}" 2>/dev/null || true
    wait "${CHROME_PID}" 2>/dev/null || true
    echo "==> Done."
}
trap cleanup EXIT INT TERM

echo "==> Starting DS-160 server on ${API_HOST}:${API_PORT}..."
PYTHONPATH=/app/src exec python -m visa_agent.server
