from __future__ import annotations

from pathlib import Path
import unittest

from visa_agent.browser.plan import compile_browser_execution_plan
from visa_agent.browser.runtime import build_runtime_plan
from visa_agent.mapping import map_dossier_to_ds160
from visa_agent.planner import build_execution_plan
from visa_agent.schema import load_dossier


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "sample_data" / "china_b1b2_sample.json"


class RuntimePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        dossier = load_dossier(SAMPLE_PATH)
        mapped = map_dossier_to_ds160(dossier)
        execution_plan = build_execution_plan(mapped)
        browser_plan = compile_browser_execution_plan(execution_plan)
        self.runtime_plan = build_runtime_plan(browser_plan)
        self.by_page = {page.page_id: page for page in self.runtime_plan.pages}

    def test_runtime_plan_resolves_fill_locators(self) -> None:
        personal_page = self.by_page["personal_page_1"]
        surname = next(item for item in personal_page.fill_instructions if item.field_id == "identity.surname")
        self.assertIsNotNone(surname.locator)
        self.assertEqual(surname.locator["strategy"], "css")
        self.assertEqual(surname.locator["input_kind"], "text")

    def test_runtime_plan_marks_review_and_block_page_pauses(self) -> None:
        travel_page = self.by_page["travel_page"]
        self.assertIn("pause_for_review", travel_page.page_stops)
        self.assertIn("pause_for_missing_data", travel_page.page_stops)

    def test_runtime_plan_keeps_global_hard_stops(self) -> None:
        self.assertIn("stop_on_captcha", self.runtime_plan.global_hard_stops)
        self.assertIn("stop_on_applicant_signature", self.runtime_plan.global_hard_stops)
        self.assertIn("stop_for_missing_locator_binding", self.runtime_plan.global_hard_stops)


if __name__ == "__main__":
    unittest.main()
