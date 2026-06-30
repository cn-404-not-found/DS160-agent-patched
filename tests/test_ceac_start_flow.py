from __future__ import annotations

import unittest

from visa_agent.browser.ceac_start_flow import (
    generate_prepare_script,
    generate_resume_commands,
    generate_status_commands,
    render_prepare_script,
    render_resume_script,
)


class CeacStartFlowTests(unittest.TestCase):
    def test_prepare_script_has_open_and_location_selection(self) -> None:
        commands = generate_prepare_script("CHINA, SHANGHAI")
        self.assertEqual(len(commands), 3)
        self.assertIn("https://ceac.state.gov/genniv/", commands[0].command)
        self.assertIn("CHINA, SHANGHAI", commands[2].command)

    def test_status_command_reads_captcha_and_location(self) -> None:
        command = generate_status_commands()[0]
        self.assertIn("captchaFilled", command.command)
        self.assertIn("locationValue", command.command)
        self.assertIn("startVisible", command.command)

    def test_resume_command_guards_on_empty_captcha(self) -> None:
        command = generate_resume_commands()[0]
        self.assertIn("CAPTCHA_EMPTY", command.command)
        self.assertIn("START_CLICKED", command.command)
        self.assertIn("ctl00_SiteContentPlaceHolder_lnkNew", command.command)

    def test_rendered_scripts_are_non_empty(self) -> None:
        self.assertIn("open https://ceac.state.gov/genniv/", render_prepare_script("CHINA, SHANGHAI"))
        self.assertIn("START_CLICKED", render_resume_script())


if __name__ == "__main__":
    unittest.main()

