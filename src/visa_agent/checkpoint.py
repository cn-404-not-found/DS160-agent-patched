"""Fill checkpoint persistence for resuming interrupted DS-160 sessions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKPOINT_FILENAME = ".ds160_checkpoint.json"


@dataclass
class FillCheckpoint:
    case_id: str
    application_id: str | None = None
    completed_pages: list[str] = field(default_factory=list)
    current_page_key: str | None = None
    updated_at: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "application_id": self.application_id,
            "completed_pages": list(self.completed_pages),
            "current_page_key": self.current_page_key,
            "updated_at": self.updated_at,
        }


def _checkpoint_path(workspace: Path) -> Path:
    return workspace / CHECKPOINT_FILENAME


def save_checkpoint(cp: FillCheckpoint, workspace: Path) -> Path:
    cp.updated_at = datetime.now(timezone.utc).isoformat()
    payload = cp.to_payload()
    dest = _checkpoint_path(workspace)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def load_checkpoint(workspace: Path) -> FillCheckpoint | None:
    dest = _checkpoint_path(workspace)
    if not dest.is_file():
        return None
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
        return FillCheckpoint(
            case_id=data["case_id"],
            application_id=data.get("application_id"),
            completed_pages=data.get("completed_pages", []),
            current_page_key=data.get("current_page_key"),
            updated_at=data.get("updated_at", ""),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def clear_checkpoint(workspace: Path) -> None:
    dest = _checkpoint_path(workspace)
    dest.unlink(missing_ok=True)


def checkpoint_workspace() -> Path:
    from visa_agent._paths import project_root
    return project_root().parent / ".checkpoint"
