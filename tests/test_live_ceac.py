from __future__ import annotations

import unittest

from visa_agent.browser.live_ceac import generate_ceac_start_commands, render_live_shell_script


class LiveCeacTests(unittest.TestCase):
    def test_live_start_commands_require_captcha_by_default(self) -> None:
        commands = generate_ceac_start_commands("CHINA, SHANGHAI")
        self.assertEqual(commands[0].step, "open_ceac")
        self.assertTrue(commands[0].executable)
        self.assertEqual(commands[2].step, "select_location")
        self.assertTrue(commands[2].executable)
        self.assertEqual(commands[3].step, "captcha_required")
        self.assertFalse(commands[3].executable)
        self.assertEqual(commands[4].step, "start_application")
        self.assertFalse(commands[4].executable)

    def test_live_start_commands_become_clickable_with_captcha(self) -> None:
        commands = generate_ceac_start_commands("CHINA, SHANGHAI", captcha_text="ABCD12")
        self.assertEqual(commands[3].step, "fill_captcha")
        self.assertTrue(commands[3].executable)
        self.assertEqual(commands[4].step, "start_application")
        self.assertTrue(commands[4].executable)

    def test_live_start_script_contains_real_ceac_ids(self) -> None:
        script = render_live_shell_script(generate_ceac_start_commands("CHINA, SHANGHAI"))
        self.assertIn("ctl00_SiteContentPlaceHolder_ucLocation_ddlLocation", script)
        self.assertIn("https://ceac.state.gov/genniv/", script)


if __name__ == "__main__":
    unittest.main()

