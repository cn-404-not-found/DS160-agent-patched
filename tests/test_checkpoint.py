"""Tests for fill checkpoint save/load/clear."""
from __future__ import annotations

import tempfile
from pathlib import Path

from visa_agent.checkpoint import (
    FillCheckpoint,
    clear_checkpoint,
    load_checkpoint,
    save_checkpoint,
)


class TestCheckpoint:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            cp = FillCheckpoint(
                case_id="CHN-001",
                application_id="AA00ABCDEF",
                completed_pages=["personal1", "personal2"],
                current_page_key="travel",
            )
            save_checkpoint(cp, ws)
            loaded = load_checkpoint(ws)
            assert loaded is not None
            assert loaded.case_id == "CHN-001"
            assert loaded.application_id == "AA00ABCDEF"
            assert loaded.completed_pages == ["personal1", "personal2"]
            assert loaded.current_page_key == "travel"
            assert loaded.updated_at

    def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as td:
            assert load_checkpoint(Path(td)) is None

    def test_clear(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            save_checkpoint(FillCheckpoint(case_id="X"), ws)
            clear_checkpoint(ws)
            assert load_checkpoint(ws) is None

    def test_corrupted_file_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            (ws / ".ds160_checkpoint.json").write_text("not json", encoding="utf-8")
            assert load_checkpoint(ws) is None

    def test_to_payload(self):
        cp = FillCheckpoint(
            case_id="T-1",
            application_id="APP001",
            completed_pages=["personal1"],
            current_page_key="personal2",
        )
        p = cp.to_payload()
        assert p["case_id"] == "T-1"
        assert p["application_id"] == "APP001"
        assert "updated_at" in p

    def test_updated_at_is_set_on_save(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            cp = FillCheckpoint(case_id="T-2")
            save_checkpoint(cp, ws)
            loaded = load_checkpoint(ws)
            assert loaded.updated_at
