#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"

cd "$ROOT_DIR"

# Ensure venv is set up
if [[ ! -x .venv/bin/python ]]; then
    echo "Setting up virtual environment..."
    bash scripts/install-deps.sh
fi

PYTHON="$ROOT_DIR/.venv/bin/python"

ensure_pip() {
    if "$PYTHON" -m pip --version >/dev/null 2>&1; then
        return 0
    fi
    echo "Bootstrapping pip in .venv..."
    "$PYTHON" -m ensurepip --upgrade
}

# Install PyInstaller if needed
if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    ensure_pip
    if ! "$PYTHON" -m pip install pyinstaller -q; then
        echo "Default pip index failed; retrying with https://pypi.org/simple ..."
        "$PYTHON" -m pip install pyinstaller -q --index-url https://pypi.org/simple
    fi
fi

MODE="${1:-onedir}"  # onedir or onefile

echo "=== Building DS-160 Visa Assistant ($MODE) ==="
echo "Source: $ROOT_DIR/src/visa_agent"
echo "Output: $DIST_DIR"

rm -rf "$BUILD_DIR" "$DIST_DIR"

"$PYTHON" -m PyInstaller \
    --name ds160-assistant \
    --"$MODE" \
    --clean \
    --noconfirm \
    --paths "$ROOT_DIR/src" \
    --add-data "$ROOT_DIR/app:app" \
    --add-data "$ROOT_DIR/src/visa_agent/dossier.schema.json:visa_agent" \
    --add-data "$ROOT_DIR/sample_data:sample_data" \
    --hidden-import visa_agent.server \
    --hidden-import visa_agent.schema \
    --hidden-import visa_agent.mapping \
    --hidden-import visa_agent.planner \
    --hidden-import visa_agent.encryption \
    --hidden-import visa_agent.checkpoint \
    --hidden-import visa_agent.audit_log \
    --hidden-import visa_agent.dom_drift \
    --hidden-import visa_agent.dossier_contract \
    --hidden-import visa_agent.draft_bundle \
    --hidden-import visa_agent.page_ids \
    --hidden-import visa_agent._paths \
    --hidden-import visa_agent.browser.cdp_client \
    --hidden-import visa_agent.browser.live_form_fill \
    --hidden-import visa_agent.browser.visible_control \
    --hidden-import visa_agent.browser.plan \
    --hidden-import visa_agent.browser.runtime \
    --hidden-import visa_agent.browser.locators \
    --hidden-import visa_agent.browser.live_ceac \
    --hidden-import visa_agent.browser.ceac_start_flow \
    --hidden-import visa_agent.browser.driver_adapter \
    --hidden-import visa_agent.browser.playwright_adapter \
    --hidden-import visa_agent.browser.visible_browser \
    --hidden-import uvicorn \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import fastapi \
    --hidden-import pydantic \
    --hidden-import cryptography \
    --hidden-import websocket \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "$BUILD_DIR" \
    src/visa_agent/__main__.py

echo ""
echo "=== Build complete ==="
if [[ "$MODE" == "onefile" ]]; then
    echo "Binary: $DIST_DIR/ds160-assistant"
    du -h "$DIST_DIR/ds160-assistant"
else
    echo "Directory: $DIST_DIR/ds160-assistant/"
    du -sh "$DIST_DIR/ds160-assistant/"
fi
echo ""
echo "Run with:"
if [[ "$MODE" == "onefile" ]]; then
    echo "  $DIST_DIR/ds160-assistant"
else
    echo "  $DIST_DIR/ds160-assistant/ds160-assistant"
fi
echo ""
echo "To open on macOS:"
if [[ "$MODE" == "onefile" ]]; then
    echo "  open $DIST_DIR"
else
    echo "  open $DIST_DIR/ds160-assistant/"
fi
