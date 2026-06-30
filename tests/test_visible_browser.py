from __future__ import annotations

import unittest

from visa_agent.browser.visible_browser import build_visible_ceac_commands, render_visible_browser_script


class VisibleBrowserTests(unittest.TestCase):
    def test_visible_browser_commands_include_chrome_launch(self) -> None:
        commands = build_visible_ceac_commands()
        self.assertEqual(commands[0].step, "open_visible_chrome")
        self.assertTrue(commands[0].executable)
        self.assertIn("google-chrome --new-window", commands[0].command)
        self.assertIn("https://ceac.state.gov/genniv/", commands[0].command)

    def test_visible_browser_script_includes_human_handoff(self) -> None:
        script = render_visible_browser_script(build_visible_ceac_commands())
        self.assertIn("google-chrome --new-window", script)
        self.assertIn("# In the visible browser:", script)


if __name__ == "__main__":
    unittest.main()

