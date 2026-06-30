from __future__ import annotations

from pathlib import Path
import unittest

from visa_agent.browser.plan import compile_browser_execution_plan
from visa_agent.mapping import map_dossier_to_ds160
from visa_agent.planner import build_execution_plan
from visa_agent.schema import load_dossier


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "sample_data" / "china_b1b2_sample.json"


class BrowserPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        dossier = load_dossier(SAMPLE_PATH)
        mapped = map_dossier_to_ds160(dossier)
        execution_plan = build_execution_plan(mapped)
        self.browser_plan = compile_browser_execution_plan(execution_plan)
        self.by_page = {page.page_id: page for page in self.browser_plan.pages}

    def test_browser_plan_batches_fields_by_expected_page(self) -> None:
        personal_fill_ids = {item.field_id for item in self.by_page["personal_page_1"].fill}
        passport_fill_ids = {item.field_id for item in self.by_page["passport_page"].fill}
        travel_review_ids = {item.field_id for item in self.by_page["travel_page"].review}
        travel_block_ids = {item.field_id for item in self.by_page["travel_page"].blocked}
        self.assertIn("identity.surname", personal_fill_ids)
        self.assertIn("passport.number", passport_fill_ids)
        self.assertIn("travel.purpose_of_trip", travel_review_ids)
        self.assertIn("travel.us_contact_phone", travel_block_ids)

    def test_browser_plan_preserves_page_save_checkpoints(self) -> None:
        self.assertEqual(self.by_page["personal_page_1"].save_checkpoint, "save_after_identity_page")
        self.assertEqual(self.by_page["travel_page"].save_checkpoint, "save_after_travel_page")
        self.assertEqual(self.by_page["work_education_present_page"].save_checkpoint, "save_after_employment_page")

    def test_browser_plan_keeps_hard_stops(self) -> None:
        self.assertIn("stop_on_captcha", self.browser_plan.hard_stops)
        self.assertIn("stop_on_applicant_signature", self.browser_plan.hard_stops)
        self.assertIn("stop_for_operator_review_queue", self.browser_plan.hard_stops)
        self.assertIn("stop_for_missing_required_data", self.browser_plan.hard_stops)


if __name__ == "__main__":
    unittest.main()

