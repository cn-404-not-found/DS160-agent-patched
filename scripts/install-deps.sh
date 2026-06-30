#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN=""

while (($# > 0)); do
  case "$1" in
    --python)
      if (($# < 2)); then
        echo "Missing value for --python" >&2
        exit 1
      fi
      PYTHON_BIN="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

resolve_python_bin() {
  if [[ -n "$PYTHON_BIN" ]]; then
    if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
      command -v "$PYTHON_BIN"
      return
    fi
    if [[ -x "$PYTHON_BIN" ]]; then
      printf '%s\n' "$PYTHON_BIN"
      return
    fi
    echo "Python not found for --python: $PYTHON_BIN" >&2
    exit 1
  fi

  local candidate
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return
    fi
  done

  echo "Python not found. Install Python 3.10+ first." >&2
  exit 1
}

require_python_310() {
  "$1" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required.")
PY
}

create_venv_with_uv() {
  if command -v uv >/dev/null 2>&1; then
    echo "Using uv to create/update .venv"
    uv venv "$VENV_DIR" --python "$1"
    return 0
  fi
  return 1
}

create_venv_with_stdlib() {
  echo "Using stdlib venv to create/update .venv"
  "$1" -m venv "$VENV_DIR"
}

install_with_uv() {
  if command -v uv >/dev/null 2>&1; then
    echo "Installing Python packages with uv"
    uv pip install --python "$VENV_DIR/bin/python" -r "$ROOT_DIR/requirements.txt"
    return 0
  fi
  return 1
}

install_with_pip() {
  echo "Installing Python packages with pip"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"
}

verify_runtime_imports() {
  "$VENV_DIR/bin/python" - <<'PY'
import fastapi
import uvicorn
print("Python runtime deps OK:", fastapi.__name__, uvicorn.__name__)
PY
}

MAIN_PYTHON="$(resolve_python_bin)"
require_python_310 "$MAIN_PYTHON"

cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/scripts"

if ! create_venv_with_uv "$MAIN_PYTHON"; then
  create_venv_with_stdlib "$MAIN_PYTHON"
fi

if ! install_with_uv; then
  install_with_pip
fi

verify_runtime_imports

cat <<EOF

Dependency install complete.

Next steps:
1. source "$VENV_DIR/bin/activate"
2. bash scripts/start.sh

EOF
