from __future__ import annotations

from pathlib import Path
import unittest

from visa_agent.mapping import map_dossier_to_ds160
from visa_agent.planner import build_execution_plan
from visa_agent.schema import load_dossier


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "sample_data" / "china_b1b2_sample.json"


class MappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dossier = load_dossier(SAMPLE_PATH)
        self.mapped = map_dossier_to_ds160(self.dossier)
        self.by_id = {item.field_id: item for item in self.mapped}
        self.plan = build_execution_plan(self.mapped)

    def test_mapping_contains_all_status_buckets(self) -> None:
        statuses = {item.status for item in self.mapped}
        self.assertIn("ready", statuses)
        self.assertIn("needs_review", statuses)
        self.assertIn("blocked", statuses)

    def test_critical_identity_field_is_ready(self) -> None:
        field = self.by_id["passport.number"]
        self.assertEqual(field.status, "ready")
        self.assertEqual(field.proposed_value, "E12345678")
        self.assertGreater(field.confidence, 0.9)

    def test_mixed_trip_purpose_needs_review(self) -> None:
        field = self.by_id["travel.purpose_of_trip"]
        self.assertEqual(field.status, "needs_review")
        self.assertEqual(field.proposed_value, "B1/B2")
        self.assertIn("Mixed business/tourism", field.notes or "")

    def test_missing_us_contact_phone_is_blocked(self) -> None:
        field = self.by_id["travel.us_contact_phone"]
        self.assertEqual(field.status, "blocked")
        self.assertIsNone(field.proposed_value)

    def test_all_fields_have_evidence_refs(self) -> None:
        for item in self.mapped:
            self.assertTrue(item.evidence_refs, msg=f"{item.field_id} is missing evidence refs")

    def test_execution_plan_includes_review_and_block_stops(self) -> None:
        self.assertIn("stop_for_operator_review_queue", self.plan.hard_stops)
        self.assertIn("stop_for_missing_required_data", self.plan.hard_stops)
        self.assertIn("stop_on_captcha", self.plan.hard_stops)
        self.assertIn("stop_on_applicant_signature", self.plan.hard_stops)

    def test_execution_plan_routes_fields_by_status(self) -> None:
        review_ids = {action.field_id for action in self.plan.review_actions}
        blocked_ids = {action.field_id for action in self.plan.blocked_actions}
        fill_ids = {action.field_id for action in self.plan.fill_actions}
        self.assertIn("travel.purpose_of_trip", review_ids)
        self.assertIn("travel.us_contact_phone", blocked_ids)
        self.assertIn("passport.number", fill_ids)


if __name__ == "__main__":
    unittest.main()
