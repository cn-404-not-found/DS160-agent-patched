"""Single entry point launcher for the DS-160 Visa Assistant.

Starts Chrome with remote debugging, launches the FastAPI server, and
opens the default browser to the unified landing page.

Usage:
    python -m visa_agent                  # development
    ./ds160-assistant                     # PyInstaller onefile binary
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from visa_agent._paths import project_root


def _find_chrome() -> str | None:
    """Locate Chrome/Chromium binary on the current platform."""
    candidates: list[str] = []
    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif sys.platform == "win32":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        candidates = [
            "google-chrome",
            "google-chrome-stable",
            "chromium-browser",
            "chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium",
        ]

    for name in candidates:
        found = shutil.which(name) if "/" not in name else (Path(name) if Path(name).exists() else None)
        if found:
            return str(found)
    return None


def _launch_chrome(cdp_port: int, profile_dir: Path, ceac_url: str) -> subprocess.Popen | None:
    chrome = _find_chrome()
    if not chrome:
        print("[ds160] Chrome/Chromium not found. Install Chrome for autofill support.")
        print("[ds160] The web UI is still available at http://127.0.0.1:8765")
        return None

    profile_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome,
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--disable-extensions",
        ceac_url,
    ]
    if sys.platform == "darwin":
        # On macOS, open Chrome via 'open -na' for proper app launch
        app_name = "Google Chrome"
        if "Chromium" in chrome:
            app_name = "Chromium"
        proc = subprocess.Popen(
            ["open", "-na", app_name, "--args"] + cmd[1:],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    print(f"[ds160] Chrome launched (CDP port {cdp_port}) -> {ceac_url}")
    return proc


def _wait_for_cdp(cdp_port: int, timeout: int = 30) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{cdp_port}/json/version", timeout=1
            )
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> int:
    cdp_port = int(os.environ.get("CDP_PORT", "9222"))
    api_port = int(os.environ.get("API_PORT", "8765"))
    api_host = os.environ.get("API_HOST", "127.0.0.1")
    ceac_url = os.environ.get("CEAC_URL", "https://ceac.state.gov/genniv/")

    profile_dir = project_root().parent / ".chrome-profile"

    print(f"[ds160] DS-160 Visa Assistant starting...")
    print(f"[ds160] Web UI: http://{api_host}:{api_port}")

    chrome_proc = _launch_chrome(cdp_port, profile_dir, ceac_url)

    def run_server():
        import uvicorn
        os.environ["CDP_PORT"] = str(cdp_port)
        os.environ["API_HOST"] = api_host
        os.environ["API_PORT"] = str(api_port)
        uvicorn.run(
            "visa_agent.server:app",
            host=api_host,
            port=api_port,
            reload=False,
            log_level="info",
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready, then open browser
    deadline = time.time() + 15
    landing_url = f"http://{api_host}:{api_port}"
    while time.time() < deadline:
        import urllib.request
        try:
            urllib.request.urlopen(f"{landing_url}/status", timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    print(f"[ds160] Opening {landing_url}")
    webbrowser.open(landing_url)

    if chrome_proc:
        if _wait_for_cdp(cdp_port, timeout=10):
            print("[ds160] Chrome CDP ready — autofill enabled.")
        else:
            print("[ds160] WARNING: Chrome CDP not ready. Autofill will fail until Chrome is running with --remote-debugging-port.")

    print("[ds160] Ready. Press Ctrl+C to stop.")

    def shutdown(signum=None, frame=None):
        print("\n[ds160] Shutting down...")
        if chrome_proc:
            chrome_proc.terminate()
            try:
                chrome_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server_thread.join()
    except KeyboardInterrupt:
        shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
