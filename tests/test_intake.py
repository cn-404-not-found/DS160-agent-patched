from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from visa_agent.dossier_contract import load_dossier_schema, missing_required_dossier_fields, validate_dossier_payload

try:
    import visa_agent.server as server_module
    from visa_agent.server import (
        DraftBundleResponse,
        FillPageRequest,
        post_dossier_document,
        post_dossier_preview,
        get_draft_bundle,
    )
    SERVER_IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
    server_module = None
    DraftBundleResponse = None
    FillPageRequest = None
    post_dossier_document = None
    post_dossier_preview = None
    get_draft_bundle = None
    SERVER_IMPORT_ERROR = exc


ROOT = Path(__file__).resolve().parents[1]
INTAKE_HTML = ROOT / "app" / "intake.html"
INTAKE_JS = ROOT / "app" / "intake.js"
FULL_DOSSIER_SAMPLE = ROOT / "sample_data" / "china_b1b2_sample.json"


def sample_dossier() -> dict[str, object]:
    return json.loads(FULL_DOSSIER_SAMPLE.read_text(encoding="utf-8"))


class DossierContractTests(unittest.TestCase):
    def test_full_dossier_sample_validates(self) -> None:
        validated = validate_dossier_payload(sample_dossier())
        self.assertEqual(validated["case_id"], "CN-B1B2-001")
        self.assertEqual(validated["identity"]["surname"], "ZHANG")

    def test_missing_required_path_is_reported(self) -> None:
        payload = sample_dossier()
        del payload["identity"]["surname"]
        missing = missing_required_dossier_fields(payload)
        self.assertIn("identity.surname", missing)

    def test_manual_form_contains_full_dossier_paths(self) -> None:
        html = INTAKE_HTML.read_text(encoding="utf-8")
        manual_form_match = re.search(r'<form id="manual-form"[\s\S]+?</form>', html)
        self.assertIsNotNone(manual_form_match)
        form_names = re.findall(r'name="([^"]+)"', manual_form_match.group(0))
        self.assertIn("case_id", form_names)
        self.assertIn("identity.birth_province", form_names)
        self.assertIn("employment_education.monthly_income_local", form_names)
        self.assertIn("security_background.explanations", form_names)
        self.assertIn("evidence_catalog", form_names)

    def test_static_page_uses_dossier_schema_and_export(self) -> None:
        script = INTAKE_JS.read_text(encoding="utf-8")
        self.assertIn("/dossier-schema", script)
        self.assertIn("/dossier/preview", script)
        self.assertIn("china-b1b2-dossier.json", script)
        self.assertIn("完整 dossier JSON 对象", script)

    def test_clipboard_copy_has_exec_command_fallback(self) -> None:
        script = INTAKE_JS.read_text(encoding="utf-8")
        self.assertIn("copyTextToClipboard", script)
        self.assertIn('document.execCommand("copy")', script)

    def test_request_model_rejects_extra_fields(self) -> None:
        if FillPageRequest is None:
            self.skipTest(f"server dependencies unavailable: {SERVER_IMPORT_ERROR}")
        with self.assertRaises(Exception):
            FillPageRequest(page_id="travel_page", extra_field="value")


@unittest.skipIf(server_module is None, f"server dependencies unavailable: {SERVER_IMPORT_ERROR}")
class DossierPreviewEndpointTests(unittest.TestCase):
    def tearDown(self) -> None:
        server_module.ACTIVE_DOSSIER_DOCUMENT = None

    def test_preview_endpoint_returns_status_summary(self) -> None:
        payload = post_dossier_preview(sample_dossier()).model_dump()
        self.assertTrue(payload["ok"])
        self.assertGreater(payload["status_counts"]["ready"], 0)
        self.assertEqual(payload["dossier"]["travel_plan"]["visa_class"], "B1/B2")

    def test_dossier_document_becomes_single_source_for_draft_bundle(self) -> None:
        post_dossier_document(sample_dossier())
        response: DraftBundleResponse = get_draft_bundle()
        bundle = response.model_dump()["bundle"]
        self.assertEqual(bundle["case_id"], "CN-B1B2-001")
        self.assertIn("summary", bundle)
        self.assertGreater(len(bundle["pages"]), 0)


if __name__ == "__main__":
    unittest.main()
