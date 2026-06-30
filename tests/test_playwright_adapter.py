from __future__ import annotations

from pathlib import Path
import unittest

from visa_agent.browser.plan import compile_browser_execution_plan
from visa_agent.browser.playwright_adapter import build_playwright_commands, render_playwright_script
from visa_agent.browser.runtime import build_runtime_plan
from visa_agent.mapping import map_dossier_to_ds160
from visa_agent.planner import build_execution_plan
from visa_agent.schema import load_dossier


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "sample_data" / "china_b1b2_sample.json"


class PlaywrightAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        dossier = load_dossier(SAMPLE_PATH)
        mapped = map_dossier_to_ds160(dossier)
        execution_plan = build_execution_plan(mapped)
        browser_plan = compile_browser_execution_plan(execution_plan)
        runtime_plan = build_runtime_plan(browser_plan)
        self.commands = build_playwright_commands(runtime_plan, "https://ceac.state.gov/genniv/")
        self.script = render_playwright_script(self.commands)

    def test_select_and_radio_are_executable(self) -> None:
        select_commands = [command for command in self.commands if command.operation == "select_by_label"]
        self.assertTrue(select_commands)
        self.assertTrue(all(command.executable for command in select_commands))

    def test_script_contains_real_playwright_actions(self) -> None:
        self.assertIn("selectOption", self.script)
        self.assertIn("getByLabel", self.script)
        self.assertIn("FINAL SIGN CHECKPOINT", self.script)

    def test_continue_steps_remain_explicitly_unbound(self) -> None:
        continue_commands = [command for command in self.commands if command.operation == "continue_to_next_page"]
        self.assertTrue(continue_commands)
        self.assertTrue(all(not command.executable for command in continue_commands))


if __name__ == "__main__":
    unittest.main()

