#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.logs"
SERVER_LOG="$LOG_DIR/server.log"
PROFILE_DIR="$ROOT_DIR/.visible-browser-profile"
REMOTE_DEBUGGING_PORT=9222
SERVER_PORT=8765
CEAC_URL="https://ceac.state.gov/genniv/"
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

resolve_python_bin() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT_DIR/.venv/bin/python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi
  echo "Python not found. Run scripts/install-deps.sh first." >&2
  exit 1
}

file_url() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve().as_uri())
PY
}

server_is_up() {
  curl -fsS "http://127.0.0.1:${SERVER_PORT}/status" >/dev/null 2>&1
}

resolve_open_cmd() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "open"
    return
  fi
  local candidate
  for candidate in xdg-open sensible-browser gio; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return
    fi
  done
  echo "No browser opener found. Install xdg-open, sensible-browser, or gio." >&2
  exit 1
}

open_url() {
  local opener="$1"
  local url="$2"
  case "$(basename "$opener")" in
    open)
      "$opener" "$url"
      ;;
    gio)
      "$opener" open "$url" >/dev/null 2>&1 &
      ;;
    *)
      "$opener" "$url" >/dev/null 2>&1 &
      ;;
  esac
}

resolve_chrome_launch() {
  case "$(uname -s)" in
    Darwin)
      local app_name="Google Chrome"
      local candidate
      for candidate in "Google Chrome" "Google Chrome Canary" "Chromium"; do
        if [[ -d "/Applications/${candidate}.app" ]]; then
          app_name="$candidate"
          break
        fi
      done
      if [[ ! -d "/Applications/${app_name}.app" ]]; then
        echo "Google Chrome/Chromium not found in /Applications. Install Chrome for DS-160 autofill." >&2
        exit 1
      fi
      printf 'open -na %q --args --remote-debugging-port=%q --user-data-dir=%q --no-first-run --disable-extensions %q\n' \
        "$app_name" "$REMOTE_DEBUGGING_PORT" "$PROFILE_DIR" "$CEAC_URL"
      ;;
    *)
      local chrome_bin=""
      local bin_candidate
      for bin_candidate in google-chrome google-chrome-stable chromium-browser chromium; do
        if command -v "$bin_candidate" >/dev/null 2>&1; then
          chrome_bin="$(command -v "$bin_candidate")"
          break
        fi
      done
      if [[ -z "$chrome_bin" ]]; then
        echo "Google Chrome/Chromium not found in PATH. Install Chrome for DS-160 autofill." >&2
        exit 1
      fi
      printf '%q --remote-debugging-port=%q --user-data-dir=%q --no-first-run --disable-extensions %q\n' \
        "$chrome_bin" "$REMOTE_DEBUGGING_PORT" "$PROFILE_DIR" "$CEAC_URL"
      ;;
  esac
}

start_chrome_debug() {
  local command
  command="$(resolve_chrome_launch)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY RUN: chrome debug launch"
    echo "$command"
    return
  fi
  eval "$command" >/dev/null 2>&1 &
  disown || true
  echo "Chrome debug window launched on port ${REMOTE_DEBUGGING_PORT}."
}

start_server() {
  local python_bin
  python_bin="$(resolve_python_bin)"
  local command=(env "PYTHONPATH=$ROOT_DIR/src" "$python_bin" -m visa_agent.server)
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY RUN: server launch"
    printf 'env PYTHONPATH="%s/src" "%s" -m visa_agent.server\n' "$ROOT_DIR" "$python_bin"
    return
  fi

  if server_is_up; then
    echo "FastAPI server is already running on http://127.0.0.1:${SERVER_PORT}"
    return
  fi

  mkdir -p "$LOG_DIR"
  nohup "${command[@]}" >"$SERVER_LOG" 2>&1 &
  local server_pid=$!
  echo "Starting FastAPI server (pid ${server_pid}), log: $SERVER_LOG"

  for _ in {1..15}; do
    if server_is_up; then
      return
    fi
    sleep 1
  done

  echo "FastAPI server did not become ready. Recent log output:" >&2
  tail -n 20 "$SERVER_LOG" >&2 || true
  exit 1
}

LANDING_URL="http://127.0.0.1:${SERVER_PORT}"
OPEN_CMD="$(resolve_open_cmd)"

if [[ "$DRY_RUN" -eq 1 ]]; then
  start_chrome_debug
  start_server
  echo "DRY RUN: open landing page $LANDING_URL"
  exit 0
fi

mkdir -p "$PROFILE_DIR"
start_chrome_debug
start_server

# Wait for server to be fully up before opening browser
sleep 2
open_url "$OPEN_CMD" "$LANDING_URL"

cat <<EOF
Startup complete.

  DS-160 签证助手:  $LANDING_URL
  FastAPI service:   http://127.0.0.1:${SERVER_PORT}
  Chrome CDP:        http://127.0.0.1:${REMOTE_DEBUGGING_PORT}/json/version

下一步：
  1. 在打开的页面中选择"填写资料"，录入申请信息
  2. 导出 dossier JSON 文件
  3. 在助手页面导入 JSON
  4. 在 Chrome 中打开 ceac.state.gov 开始填表
  5. 回到助手页面，点击填入按钮
EOF
