from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class VisibleBrowserCommand:
    step: str
    executable: bool
    command: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_visible_ceac_commands(
    url: str = "https://ceac.state.gov/genniv/",
    profile_dir: str = ".visible-browser-profile",
    remote_debugging_port: int = 9222,
) -> list[VisibleBrowserCommand]:
    profile_path = Path(profile_dir)
    chrome_cmd = (
        "mkdir -p "
        + _shell_quote(str(profile_path))
        + " && "
        + "nohup setsid google-chrome --new-window "
        + f"--remote-debugging-port={remote_debugging_port} "
        + "--user-data-dir="
        + _shell_quote(str(profile_path))
        + " "
        + _shell_quote(url)
        + " >/dev/null 2>&1 < /dev/null &"
    )
    return [
        VisibleBrowserCommand(
            step="open_visible_chrome",
            executable=True,
            command=chrome_cmd,
            notes="Open a real desktop Chrome window the human can see.",
        ),
        VisibleBrowserCommand(
            step="human_select_location_and_read_captcha",
            executable=False,
            command="# In the visible browser: confirm the location, read the captcha, and tell the agent the captcha text.",
            notes="This step is intentionally human-visible and human-driven.",
        ),
    ]


def build_visible_browser_status_commands(
    remote_debugging_port: int = 9222,
    expected_url_substring: str = "ceac.state.gov/genniv",
) -> list[VisibleBrowserCommand]:
    version_url = f"http://127.0.0.1:{remote_debugging_port}/json/version"
    list_url = f"http://127.0.0.1:{remote_debugging_port}/json/list"
    return [
        VisibleBrowserCommand(
            step="probe_debug_endpoint",
            executable=True,
            command=f"curl -s {version_url}",
            notes="Check whether the visible Chrome remote debugging port is reachable.",
        ),
        VisibleBrowserCommand(
            step="probe_open_tabs",
            executable=True,
            command=(
                "python - <<'PY'\n"
                "import json, urllib.request, urllib.error\n"
                "try:\n"
                f"    tabs = json.loads(urllib.request.urlopen({json.dumps(list_url)}).read().decode())\n"
                f"    matches = [{{'title': tab.get('title'), 'url': tab.get('url')}} for tab in tabs if {json.dumps(expected_url_substring)} in (tab.get('url') or '')]\n"
                "    print(json.dumps({'status': 'OK', 'matching_tabs': matches, 'tab_count': len(tabs)}, ensure_ascii=False))\n"
                "except urllib.error.URLError as exc:\n"
                "    print(json.dumps({'status': 'NOT_REACHABLE', 'error': str(exc)}, ensure_ascii=False))\n"
                "PY"
            ),
            notes="Verify that a CEAC tab is open in the visible browser.",
        ),
    ]


def render_visible_browser_manifest(commands: list[VisibleBrowserCommand]) -> str:
    return json.dumps([command.to_dict() for command in commands], indent=2, ensure_ascii=False)


def render_visible_browser_script(commands: list[VisibleBrowserCommand]) -> str:
    return "\n".join(command.command for command in commands)


def render_visible_browser_status_script(
    remote_debugging_port: int = 9222,
    expected_url_substring: str = "ceac.state.gov/genniv",
) -> str:
    return render_visible_browser_script(
        build_visible_browser_status_commands(
            remote_debugging_port=remote_debugging_port,
            expected_url_substring=expected_url_substring,
        )
    )
