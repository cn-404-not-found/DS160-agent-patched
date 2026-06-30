from __future__ import annotations

from pathlib import Path
import unittest

from visa_agent.browser.driver_adapter import build_agent_browser_commands, render_agent_browser_script
from visa_agent.browser.plan import compile_browser_execution_plan
from visa_agent.browser.runtime import build_runtime_plan
from visa_agent.mapping import map_dossier_to_ds160
from visa_agent.planner import build_execution_plan
from visa_agent.schema import load_dossier


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "sample_data" / "china_b1b2_sample.json"


class DriverAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        dossier = load_dossier(SAMPLE_PATH)
        mapped = map_dossier_to_ds160(dossier)
        execution_plan = build_execution_plan(mapped)
        browser_plan = compile_browser_execution_plan(execution_plan)
        runtime_plan = build_runtime_plan(browser_plan)
        self.commands = build_agent_browser_commands(runtime_plan, "https://ceac.state.gov/genniv/")
        self.script = render_agent_browser_script(self.commands)

    def test_driver_commands_open_session_and_snapshot(self) -> None:
        commands = [command.command for command in self.commands]
        self.assertIn("agent-browser open 'https://ceac.state.gov/genniv/'", commands)
        self.assertIn("agent-browser wait --load networkidle", commands)
        self.assertIn("agent-browser snapshot -i", commands)

    def test_driver_script_contains_fill_and_pause_lines(self) -> None:
        self.assertIn("agent-browser find label '#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_SURNAME' fill 'ZHANG'", self.script)
        self.assertIn("# REVIEW REQUIRED travel.purpose_of_trip", self.script)
        self.assertIn("# BLOCKED travel.us_contact_phone", self.script)

    def test_select_fields_are_explicitly_marked_non_executable(self) -> None:
        select_commands = [command for command in self.commands if command.operation == "select_by_label"]
        self.assertTrue(select_commands)
        self.assertTrue(all(not command.executable for command in select_commands))


if __name__ == "__main__":
    unittest.main()

