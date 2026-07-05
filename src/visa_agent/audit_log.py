"""Structured JSON-lines audit log for DS-160 fill operations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _audit_dir() -> Path:
    from visa_agent._paths import project_root
    return project_root().parent / ".ds160" / "logs"


def _today_log() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _audit_dir() / f"ds160-{today}.jsonl"


def _write_event(level: str, event: str, data: dict) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        **data,
    }
    dest = _today_log()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_page_fill(
    case_id: str,
    page_key: str,
    filled: int,
    missing: int,
    application_id: str | None = None,
    ok: bool = True,
) -> None:
    _write_event(
        "info" if ok else "error",
        "page_fill",
        {
            "case_id": case_id,
            "application_id": application_id,
            "page_key": page_key,
            "filled": filled,
            "missing": missing,
            "ok": ok,
        },
    )


def log_server_start(cdp_port: int, api_port: int) -> None:
    _write_event("info", "server_start", {"cdp_port": cdp_port, "api_port": api_port})


def log_server_stop() -> None:
    _write_event("info", "server_stop", {})


def log_dossier_import(case_id: str, encrypted: bool = False) -> None:
    _write_event("info", "dossier_import", {"case_id": case_id, "encrypted": encrypted})


def log_drift_warning(page_key: str, expected: int, found: int, missing_selectors: list[str]) -> None:
    _write_event(
        "warn",
        "selector_drift",
        {
            "page_key": page_key,
            "expected": expected,
            "found": found,
            "missing_selectors": missing_selectors[:10],
        },
    )


def read_recent_logs(limit: int = 50) -> list[dict]:
    dest = _today_log()
    if not dest.is_file():
        return []
    lines = dest.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in reversed(lines):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= limit:
            break
    return entries
