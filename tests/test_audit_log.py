"""Tests for audit log writing and reading."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from visa_agent.audit_log import (
    log_dossier_import,
    log_drift_warning,
    log_page_fill,
    log_server_start,
    read_recent_logs,
)


class TestAuditLog:
    def test_write_and_read_logs(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("visa_agent.audit_log._audit_dir", return_value=Path(td)):
                with patch("visa_agent.audit_log._today_log", return_value=Path(td) / "ds160-test.jsonl"):
                    log_server_start(9222, 8765)
                    log_dossier_import("CASE-1")
                    log_page_fill("CASE-1", "personal1", 15, 2, application_id="AA00XX", ok=True)
                    log_page_fill("CASE-1", "personal2", 20, 0, application_id="AA00XX", ok=True)
                    log_drift_warning("travel", 4, 3, ["input[name$='missing']"])

                    entries = read_recent_logs(limit=50)
                    assert len(entries) == 5
                    assert entries[0]["event"] == "selector_drift"
                    assert entries[1]["event"] == "page_fill"
                    assert entries[2]["event"] == "page_fill"
                    assert entries[3]["event"] == "dossier_import"
                    assert entries[4]["event"] == "server_start"

    def test_file_created_on_first_write(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "ds160-test.jsonl"
            with patch("visa_agent.audit_log._today_log", return_value=log_path):
                log_server_start(9222, 8765)
                assert log_path.is_file()
                content = log_path.read_text(encoding="utf-8")
                assert "server_start" in content
                assert "9222" in content

    def test_empty_logs_when_file_missing(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("visa_agent.audit_log._today_log", return_value=Path(td) / "nonexistent.jsonl"):
                assert read_recent_logs() == []

    def test_corrupted_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "ds160-test.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text('not json\n{"ts":"","level":"info","event":"test"}\n', encoding="utf-8")
            with patch("visa_agent.audit_log._today_log", return_value=log_path):
                entries = read_recent_logs()
                assert len(entries) == 1
                assert entries[0]["event"] == "test"

    def test_limit_respected(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "ds160-test.jsonl"
            with patch("visa_agent.audit_log._today_log", return_value=log_path):
                for i in range(10):
                    log_server_start(9222, 8765)
                entries = read_recent_logs(limit=3)
                assert len(entries) == 3
