from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from visa_agent.draft_bundle import build_draft_bundle, export_draft_bundle_file
from visa_agent.schema import load_dossier


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "sample_data" / "china_b1b2_sample.json"
FULL_FAKE_SAMPLE_PATH = ROOT / "sample_data" / "china_b1b2_fake_test.json"


class DraftBundleTests(unittest.TestCase):
    def test_build_bundle_has_page_labels(self) -> None:
        dossier = load_dossier(SAMPLE_PATH)
        bundle = build_draft_bundle(dossier)
        labels = {page["label"] for page in bundle["pages"]}
        self.assertIn("Personal 1", labels)
        self.assertIn("Travel", labels)

    def test_full_fake_dossier_sample_also_builds_bundle(self) -> None:
        dossier = load_dossier(FULL_FAKE_SAMPLE_PATH)
        bundle = build_draft_bundle(dossier)
        labels = {page["label"] for page in bundle["pages"]}
        self.assertIn("Personal 1", labels)
        self.assertIn("Travel", labels)

    def test_export_bundle_writes_js_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "draft_bundle.js"
            export_draft_bundle_file(SAMPLE_PATH, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("window.DS160_DRAFT_BUNDLE =", text)


if __name__ == "__main__":
    unittest.main()
