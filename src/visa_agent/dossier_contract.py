from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from visa_agent.schema import ApplicantDossier, load_dossier_payload


def _schema_path() -> Path:
    return Path(__file__).with_name("dossier.schema.json")


@lru_cache(maxsize=1)
def load_dossier_schema() -> dict[str, Any]:
    return json.loads(_schema_path().read_text(encoding="utf-8"))


def dossier_to_dict(dossier: ApplicantDossier) -> dict[str, object]:
    payload = asdict(dossier)
    payload["evidence_catalog"] = list(payload["evidence_catalog"].values())
    return payload


def validate_dossier_payload(payload: dict[str, Any]) -> dict[str, Any]:
    dossier = load_dossier_payload(payload)
    return dossier_to_dict(dossier)


def dossier_field_errors(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    try:
        load_dossier_payload(payload)
    except Exception as exc:
        errors["dossier"] = str(exc)
    return errors


def missing_required_dossier_fields(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    schema = load_dossier_schema()
    _collect_missing(schema, payload, "", missing)
    return missing


def _collect_missing(schema: dict[str, Any], value: Any, prefix: str, missing: list[str]) -> None:
    if schema.get("type") != "object":
        return
    if not isinstance(value, dict):
        missing.append(prefix or "dossier")
        return
    for name in schema.get("required", []):
        path = f"{prefix}.{name}" if prefix else name
        current = value.get(name)
        if current in (None, ""):
            missing.append(path)
            continue
        child_schema = schema.get("properties", {}).get(name, {})
        _collect_missing(child_schema, current, path, missing)
