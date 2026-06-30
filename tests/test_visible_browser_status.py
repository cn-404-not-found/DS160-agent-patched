from __future__ import annotations

import unittest

from visa_agent.browser.visible_browser import (
    build_visible_browser_status_commands,
    render_visible_browser_status_script,
)


class VisibleBrowserStatusTests(unittest.TestCase):
    def test_status_commands_include_debug_probe_and_tab_probe(self) -> None:
        commands = build_visible_browser_status_commands(remote_debugging_port=9222)
        self.assertEqual(commands[0].step, "probe_debug_endpoint")
        self.assertIn("http://127.0.0.1:9222/json/version", commands[0].command)
        self.assertEqual(commands[1].step, "probe_open_tabs")
        self.assertIn("ceac.state.gov/genniv", commands[1].command)

    def test_status_script_contains_json_list_probe(self) -> None:
        script = render_visible_browser_status_script(remote_debugging_port=9222)
        self.assertIn("/json/version", script)
        self.assertIn("/json/list", script)


if __name__ == "__main__":
    unittest.main()

