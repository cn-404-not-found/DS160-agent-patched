"""Local FastAPI server bridging the DS-160 assistant frontend to Chrome via CDP."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

# Allow running directly: python -m visa_agent.server
sys.path.insert(0, str(Path(__file__).parent.parent))

from visa_agent._paths import app_dir as _app_dir, project_root as _project_root, sample_data_dir as _sample_data_dir

PROJECT_ROOT = _project_root()
APP_DIR = _app_dir()

from visa_agent.browser.cdp_client import list_debug_targets
from visa_agent.browser.live_form_fill import (
    _PAGE_FILL_HANDLERS,
    detect_current_page,
    extract_application_id,
    fill_and_continue,
    fill_current_supported_page,
    save_current_page,
)
from visa_agent.dossier_contract import (
    dossier_to_dict,
    load_dossier_schema,
    validate_dossier_payload,
)
from visa_agent.audit_log import (
    log_dossier_import,
    log_page_fill,
    read_recent_logs,
)
from visa_agent.checkpoint import (
    FillCheckpoint,
    checkpoint_workspace,
    load_checkpoint,
    save_checkpoint,
    clear_checkpoint,
)
from visa_agent.dom_drift import check_page_selectors
from visa_agent.draft_bundle import build_draft_bundle
from visa_agent.encryption import encrypt_dossier_json, is_encrypted_dossier
from visa_agent.mapping import map_dossier_to_ds160
from visa_agent.page_ids import PAGE_ID_NORMALIZE, bundle_page_id
from visa_agent.planner import build_execution_plan
from visa_agent.schema import load_dossier, load_dossier_payload

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))
DOSSIER_PATH = os.environ.get(
    "DOSSIER_PATH",
    str(_sample_data_dir() / "china_b1b2_sample.json"),
)
ACTIVE_DOSSIER_DOCUMENT: dict[str, Any] | None = None

app = FastAPI(title="DS-160 Local Fill Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets (CSS, JS) from the app directory
if APP_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=str(APP_DIR)), name="app_static")


@app.get("/", response_class=HTMLResponse)
def get_landing():
    """Unified landing page linking intake and assistant."""
    if (APP_DIR / "index.html").is_file():
        return HTMLResponse((APP_DIR / "index.html").read_text(encoding="utf-8"))
    # Fallback inline landing page
    return HTMLResponse("""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DS-160 签证助手</title>
<style>
:root{--bg:#0a0a0f;--surface:#141420;--text:#e0e0e0;--accent:#6fcf97;--accent2:#5b9bd5}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);display:flex;align-items:center;justify-content:center;min-height:100vh}
header{position:fixed;top:0;left:0;right:0;padding:1.5rem 2rem;border-bottom:1px solid #222;display:flex;align-items:center;gap:1rem}
header h1{font-size:1.1rem;font-weight:600}
header span.ver{color:#555;font-size:.8rem}
main{display:flex;gap:2rem;max-width:800px;padding:2rem;margin-top:2rem}
.card{background:var(--surface);border-radius:12px;padding:2.5rem 2rem;text-align:center;flex:1;border:1px solid #222;transition:border-color .2s}
.card:hover{border-color:var(--accent)}
.card .step{display:inline-block;background:#1a1a2e;color:var(--accent2);font-size:.75rem;padding:.25rem .75rem;border-radius:99px;margin-bottom:1rem;font-weight:600}
.card h2{font-size:1.25rem;margin-bottom:.75rem}
.card p{color:#888;margin-bottom:2rem;font-size:.9rem;line-height:1.6}
.card a{display:inline-block;padding:.7rem 2rem;border-radius:6px;text-decoration:none;font-weight:600;font-size:.9rem}
.card a.primary{background:var(--accent);color:#000}
.card a.secondary{background:var(--accent2);color:#fff}
.features{position:fixed;bottom:1.5rem;left:0;right:0;text-align:center;color:#444;font-size:.75rem}
.features span{margin:0 .75rem}
</style>
</head>
<body>
<header><h1>DS-160 签证助手</h1><span class="ver">China B1/B2</span></header>
<main>
<div class="card"><span class="step">第 1 步</span><h2>采集申请资料</h2><p>手动填写申请人护照信息、旅行计划、工作教育、家庭背景，生成统一申请资料文件。</p><a class="secondary" href="/intake">填写资料</a></div>
<div class="card"><span class="step">第 2 步</span><h2>自动填入表单</h2><p>导入资料文件，通过浏览器自动填写 DS-160 表格。支持逐页填写、一键翻页、全部自动执行。</p><a class="primary" href="/assistant">开始填写</a></div>
</main>
<footer class="features"><span>加密存储</span><span>断点续填</span><span>18 页支持</span><span>DOM 检测</span></footer>
</body>
</html>""")


@app.get("/intake", response_class=HTMLResponse)
def get_intake():
    """Serve the DS-160 intake page."""
    html = (APP_DIR / "intake.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/assistant", response_class=HTMLResponse)
def get_assistant():
    """Serve the DS-160 fill assistant page."""
    html = (APP_DIR / "ds160-assistant.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class FillPageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_id: str | None = None  # if None, auto-detect from current browser URL


class FillPageResponse(BaseModel):
    ok: bool
    page_key: str
    filled: list[str]
    missing: list[str]
    message: str
    application_id: str | None = None


class FillContinueResponse(BaseModel):
    ok: bool
    page_key: str
    new_page_key: str | None
    filled: list[str]
    missing: list[str]
    message: str
    application_id: str | None = None


class StatusResponse(BaseModel):
    connected: bool
    cdp_port: int
    open_tabs: int
    ceac_tab_found: bool
    dossier_loaded: bool
    dossier_path: str
    dossier_document_loaded: bool
    application_id: str | None = None


class DetectPageResponse(BaseModel):
    page_key: str
    url: str
    title: str
    application_id: str | None = None


class DossierPreviewResponse(BaseModel):
    ok: bool
    dossier: dict[str, Any]
    status_counts: dict[str, int]
    review_items: list[dict[str, Any]]
    blocked_items: list[dict[str, Any]]
    top_fill_fields: list[dict[str, Any]]
    hard_stops: list[str]
    page_count: int


class DossierDocumentResponse(BaseModel):
    ok: bool
    dossier_document: dict[str, Any]
    case_id: str


class DraftBundleResponse(BaseModel):
    ok: bool
    bundle: dict[str, Any]


class DossierSchemaResponse(BaseModel):
    ok: bool
    schema_document: dict[str, Any]


class DossierPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    identity: dict[str, Any]
    travel_plan: dict[str, Any]
    employment_education: dict[str, Any]
    family_contacts: dict[str, Any]
    security_background: dict[str, Any]
    evidence_catalog: list[dict[str, Any]] = []
    personal_contact: dict[str, Any] | None = None
    previous_travel: dict[str, Any] | None = None


class DossierEncryptRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    passphrase: str
    payload: dict[str, Any] | None = None


class DossierEncryptResponse(BaseModel):
    ok: bool
    encrypted_payload: dict[str, Any]


class DossierDecryptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    encrypted_payload: dict[str, Any]
    passphrase: str


class DossierDecryptResponse(BaseModel):
    ok: bool
    dossier_document: dict[str, Any]
    case_id: str


class CheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: str | None = None
    completed_pages: list[str] = []
    current_page_key: str | None = None


class CheckpointResponse(BaseModel):
    ok: bool
    checkpoint: dict[str, Any] | None


class DossierValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str | None = None
    identity: dict[str, Any] | None = None
    travel_plan: dict[str, Any] | None = None
    employment_education: dict[str, Any] | None = None
    family_contacts: dict[str, Any] | None = None
    security_background: dict[str, Any] | None = None
    evidence_catalog: list[dict[str, Any]] | None = None
    personal_contact: dict[str, Any] | None = None
    previous_travel: dict[str, Any] | None = None


class DossierValidateResponse(BaseModel):
    ok: bool
    errors: list[dict[str, str]]
    warnings: list[dict[str, str]]


class AuditLogResponse(BaseModel):
    ok: bool
    entries: list[dict[str, Any]]


class DriftCheckResponse(BaseModel):
    ok: bool
    page_key: str
    total_expected: int
    found: int
    missing: list[str]
    healthy: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_dossier():
    if ACTIVE_DOSSIER_DOCUMENT is not None:
        try:
            return load_dossier_payload(ACTIVE_DOSSIER_DOCUMENT)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Cannot build dossier from active document: {exc}")
    try:
        return load_dossier(DOSSIER_PATH)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cannot load dossier: {exc}")


def _check_cdp() -> list[dict[str, Any]]:
    try:
        return list_debug_targets(port=CDP_PORT)
    except Exception:
        return []


def _has_ceac_tab(tabs: list[dict[str, Any]]) -> bool:
    return any("ceac.state.gov" in (t.get("url") or "") for t in tabs)


def _current_application_id() -> str | None:
    try:
        result = extract_application_id()
        if result.ok:
            return str(result.payload.get("application_id") or "")
    except Exception:
        return None
    return None


def _save_detected_application_id(application_id: str | None, current_page_key: str | None = None) -> None:
    if not application_id:
        return
    try:
        dossier = _load_dossier()
        existing = load_checkpoint(checkpoint_workspace())
        cp = FillCheckpoint(
            case_id=dossier.case_id,
            application_id=application_id,
            completed_pages=list(existing.completed_pages) if existing else [],
            current_page_key=current_page_key or (existing.current_page_key if existing else None),
        )
        save_checkpoint(cp, checkpoint_workspace())
    except Exception:
        pass


def _build_preview_payload(dossier) -> DossierPreviewResponse:
    mapped = map_dossier_to_ds160(dossier)
    execution_plan = build_execution_plan(mapped)
    draft_bundle = build_draft_bundle(dossier)
    status_counts = {"ready": 0, "needs_review": 0, "blocked": 0}
    for field in mapped:
        status_counts[field.status] = status_counts.get(field.status, 0) + 1
    review_items = [field.to_dict() for field in mapped if field.status == "needs_review"]
    blocked_items = [field.to_dict() for field in mapped if field.status == "blocked"]
    top_fill_fields = [field.to_dict() for field in mapped if field.status == "ready"][:8]
    return DossierPreviewResponse(
        ok=True,
        dossier=dossier_to_dict(dossier),
        status_counts=status_counts,
        review_items=review_items,
        blocked_items=blocked_items,
        top_fill_fields=top_fill_fields,
        hard_stops=list(execution_plan.hard_stops),
        page_count=int(draft_bundle["summary"]["page_count"]),
    )


def _coerce_active_document(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    dossier_payload = validate_dossier_payload(payload)
    dossier = load_dossier_payload(dossier_payload)
    return dossier_payload, dossier.case_id


# Map from page_id (as used in the frontend bundle) to fill function
_PAGE_FILL_MAP = {
    "personal_page_1": "personal1",
    "personal_page_2": "personal2",
    "personal1": "personal1",
    "personal2": "personal2",
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/status", response_model=StatusResponse)
def get_status():
    """Check CDP connection and dossier availability."""
    tabs = _check_cdp()
    dossier_ok = Path(DOSSIER_PATH).exists()
    application_id = _current_application_id() if _has_ceac_tab(tabs) else None
    _save_detected_application_id(application_id)
    return StatusResponse(
        connected=len(tabs) > 0,
        cdp_port=CDP_PORT,
        open_tabs=len(tabs),
        ceac_tab_found=_has_ceac_tab(tabs),
        dossier_loaded=dossier_ok,
        dossier_path=DOSSIER_PATH,
        dossier_document_loaded=ACTIVE_DOSSIER_DOCUMENT is not None,
        application_id=application_id,
    )


@app.get("/detect-page", response_model=DetectPageResponse)
def get_detect_page():
    """Detect which DS-160 page is currently open in the browser."""
    tabs = _check_cdp()
    if not tabs:
        raise HTTPException(status_code=503, detail="Chrome not reachable on CDP port")
    try:
        result = detect_current_page()
        application_id = result.payload.get("application_id")
        page_key = result.payload.get("page_key", "unsupported")
        _save_detected_application_id(application_id, current_page_key=bundle_page_id(page_key) or page_key)
        return DetectPageResponse(
            page_key=page_key,
            url=result.payload.get("url", ""),
            title=result.payload.get("title", ""),
            application_id=application_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/dossier/preview", response_model=DossierPreviewResponse)
def post_dossier_preview(req: DossierPreviewRequest):
    """Validate a full dossier payload and return preview status."""
    try:
        payload = validate_dossier_payload(dict(req.model_dump()))
        dossier = load_dossier_payload(payload)
        return _build_preview_payload(dossier)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/dossier-schema", response_model=DossierSchemaResponse)
def get_dossier_schema():
    """Return the canonical dossier schema used by intake and execution flows."""
    return DossierSchemaResponse(ok=True, schema_document=load_dossier_schema())


@app.post("/dossier-document", response_model=DossierDocumentResponse)
def post_dossier_document(req: DossierPreviewRequest):
    """Set the active dossier document used by the fill assistant."""
    global ACTIVE_DOSSIER_DOCUMENT
    payload = dict(req.model_dump())
    ACTIVE_DOSSIER_DOCUMENT, case_id = _coerce_active_document(payload)
    log_dossier_import(case_id)
    return DossierDocumentResponse(
        ok=True,
        dossier_document=ACTIVE_DOSSIER_DOCUMENT,
        case_id=case_id,
    )


@app.get("/dossier-document", response_model=DossierDocumentResponse)
def get_dossier_document():
    """Return the currently loaded dossier document."""
    if ACTIVE_DOSSIER_DOCUMENT is None:
        raise HTTPException(status_code=404, detail="No dossier document loaded")
    dossier = _load_dossier()
    return DossierDocumentResponse(
        ok=True,
        dossier_document=ACTIVE_DOSSIER_DOCUMENT,
        case_id=dossier.case_id,
    )


@app.post("/dossier-document/encrypt", response_model=DossierEncryptResponse)
def post_dossier_encrypt(req: DossierEncryptRequest):
    """Encrypt the active dossier document with a passphrase."""
    doc = req.payload if req.payload is not None else ACTIVE_DOSSIER_DOCUMENT
    if doc is None:
        raise HTTPException(status_code=404, detail="No dossier document loaded")
    if len(req.passphrase) < 8:
        raise HTTPException(status_code=400, detail="Passphrase must be at least 8 characters")
    plaintext = json.dumps(doc, ensure_ascii=False)
    encrypted = encrypt_dossier_json(plaintext, req.passphrase)
    return DossierEncryptResponse(
        ok=True,
        encrypted_payload=json.loads(encrypted),
    )


@app.post("/dossier-document/decrypt", response_model=DossierDecryptResponse)
def post_dossier_decrypt(req: DossierDecryptRequest):
    """Decrypt an encrypted dossier and set it as the active document."""
    global ACTIVE_DOSSIER_DOCUMENT
    from visa_agent.encryption import decrypt_dossier_json

    if not is_encrypted_dossier(req.encrypted_payload):
        raise HTTPException(status_code=400, detail="Payload is not an encrypted dossier")
    try:
        encrypted_json = json.dumps(req.encrypted_payload, ensure_ascii=False)
        plaintext = decrypt_dossier_json(encrypted_json, req.passphrase)
    except Exception:
        raise HTTPException(status_code=400, detail="Decryption failed. Wrong passphrase or corrupted data.")
    dossier_payload = json.loads(plaintext)
    ACTIVE_DOSSIER_DOCUMENT, case_id = _coerce_active_document(dossier_payload)
    log_dossier_import(case_id, encrypted=True)
    return DossierDecryptResponse(
        ok=True,
        dossier_document=ACTIVE_DOSSIER_DOCUMENT,
        case_id=case_id,
    )


# ---------------------------------------------------------------------------
# Checkpoint endpoints
# ---------------------------------------------------------------------------


@app.get("/fill/checkpoint", response_model=CheckpointResponse)
def get_fill_checkpoint():
    """Return the current fill checkpoint if one exists."""
    cp = load_checkpoint(checkpoint_workspace())
    if cp is None:
        return CheckpointResponse(ok=True, checkpoint=None)
    return CheckpointResponse(ok=True, checkpoint=cp.to_payload())


@app.post("/fill/checkpoint", response_model=CheckpointResponse)
def post_fill_checkpoint(req: CheckpointRequest):
    """Save a fill checkpoint for resuming later."""
    dossier = _load_dossier()
    cp = FillCheckpoint(
        case_id=dossier.case_id,
        application_id=req.application_id,
        completed_pages=req.completed_pages,
        current_page_key=req.current_page_key,
    )
    save_checkpoint(cp, checkpoint_workspace())
    return CheckpointResponse(ok=True, checkpoint=cp.to_payload())


@app.delete("/fill/checkpoint", response_model=CheckpointResponse)
def delete_fill_checkpoint():
    """Clear the stored fill checkpoint."""
    clear_checkpoint(checkpoint_workspace())
    return CheckpointResponse(ok=True, checkpoint=None)


# ---------------------------------------------------------------------------
# Dossier validation endpoint
# ---------------------------------------------------------------------------


_DS160_FIELD_CONSTRAINTS: dict[str, int] = {
    "identity.surname": 33,
    "identity.given_names": 33,
    "identity.passport_number": 20,
    "identity.national_id_number": 20,
    "identity.us_social_security_number": 9,
    "identity.us_taxpayer_id_number": 9,
    "travel_plan.us_contact_phone": 20,
    "family_contacts.father_full_name": 100,
    "family_contacts.mother_full_name": 100,
    "family_contacts.spouse_full_name": 100,
    "employment_education.current_employer_name": 100,
    "employment_education.current_job_title": 100,
    "employment_education.school_name": 100,
}


def _get_nested_error(d: dict, path: str) -> str | None:
    parts = path.split(".")
    current: Any = d
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if current is None or (isinstance(current, str) and not current.strip()):
        return None
    return str(current)


@app.post("/dossier/validate", response_model=DossierValidateResponse)
def post_dossier_validate(req: DossierValidateRequest):
    """Run DS-160 field-level validation on a partial or full dossier payload."""
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    data = {k: v for k, v in req.model_dump().items() if v is not None}

    for field_path, max_len in _DS160_FIELD_CONSTRAINTS.items():
        value = _get_nested_error(data, field_path)
        if value and len(value) > max_len:
            errors.append({
                "field": field_path,
                "message": f"Exceeds {max_len} character limit (currently {len(value)} chars).",
            })

    # Check date format validity
    date_paths = ["identity.date_of_birth", "identity.passport_issue_date",
                  "identity.passport_expiration_date", "travel_plan.intended_arrival_date"]
    for fp in date_paths:
        value = _get_nested_error(data, fp)
        if value:
            import re
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
                errors.append({"field": fp, "message": "Use YYYY-MM-DD date format."})

    # Passport checks
    pn = _get_nested_error(data, "identity.passport_number")
    if pn and not re.match(r"^[A-Za-z0-9]+$", pn):
        errors.append({"field": "identity.passport_number", "message": "Passport number should be alphanumeric."})

    return DossierValidateResponse(ok=len(errors) == 0, errors=errors, warnings=warnings)


@app.get("/audit-log", response_model=AuditLogResponse)
def get_audit_log(limit: int = 50):
    """Return recent audit log entries."""
    return AuditLogResponse(ok=True, entries=read_recent_logs(limit=limit))


@app.get("/dom-drift", response_model=DriftCheckResponse)
def get_dom_drift(page_key: str | None = None):
    """Check whether expected DS-160 selectors are present in the current DOM."""
    if not page_key:
        try:
            detected = detect_current_page()
            page_key = detected.payload.get("page_key", "")
        except Exception:
            raise HTTPException(status_code=503, detail="Cannot detect current page. Specify page_key parameter.")
    try:
        report = check_page_selectors(page_key, CDP_PORT)
        if report.total_expected == 0:
            return DriftCheckResponse(
                ok=True, page_key=page_key,
                total_expected=0, found=0, missing=[], healthy=True,
            )
        from visa_agent.audit_log import log_drift_warning
        if not report.healthy:
            log_drift_warning(page_key, report.total_expected, report.found, report.missing)
        return DriftCheckResponse(
            ok=report.healthy,
            page_key=page_key,
            total_expected=report.total_expected,
            found=report.found,
            missing=report.missing,
            healthy=report.healthy,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Drift check failed: {exc}")


@app.get("/draft-bundle", response_model=DraftBundleResponse)
def get_draft_bundle():
    """Build the assistant bundle from the active dossier document or legacy dossier."""
    dossier = _load_dossier()
    return DraftBundleResponse(ok=True, bundle=build_draft_bundle(dossier))


@app.post("/fill-page", response_model=FillPageResponse)
def post_fill_page(req: FillPageRequest):
    """Fill the specified (or currently open) DS-160 page via CDP."""
    tabs = _check_cdp()
    if not tabs:
        raise HTTPException(status_code=503, detail="Chrome not reachable on CDP port. Launch Chrome with --remote-debugging-port=9222")

    dossier = _load_dossier()

    # Resolve page_id → canonical key
    page_id = req.page_id
    # Normalize frontend page_id (e.g. "personal_page_1" → "personal1")
    if page_id:
        canonical = PAGE_ID_NORMALIZE.get(page_id, page_id)
    else:
        # Auto-detect from browser URL
        try:
            detected = detect_current_page()
            canonical = detected.payload.get("page_key")
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Cannot detect current page: {exc}")

    try:
        handler = _PAGE_FILL_HANDLERS.get(canonical) if canonical else None
        if handler:
            result = handler(dossier)
        else:
            # Fallback: try auto-detect fill
            result = fill_current_supported_page(dossier)

        filled = result.payload.get("filled") or []
        missing = result.payload.get("missing") or []
        application_id = _current_application_id()
        result_page_key = canonical or result.payload.get("page_key", "unsupported")
        _save_detected_application_id(application_id, current_page_key=bundle_page_id(result_page_key) or result_page_key)
        log_page_fill(dossier.case_id, result_page_key, len(filled), len(missing), application_id=application_id, ok=result.ok)
        return FillPageResponse(
            ok=result.ok,
            page_key=result_page_key,
            filled=filled,
            missing=missing,
            message=f"Filled {len(filled)} fields, {len(missing)} missing.",
            application_id=application_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/fill-and-continue", response_model=FillContinueResponse)
def post_fill_and_continue(req: FillPageRequest):
    """Fill the current page, save, and click Next to advance to the next page."""
    tabs = _check_cdp()
    if not tabs:
        raise HTTPException(status_code=503, detail="Chrome not reachable on CDP port. Launch Chrome with --remote-debugging-port=9222")

    dossier = _load_dossier()

    canonical = PAGE_ID_NORMALIZE.get(req.page_id, req.page_id) if req.page_id else None
    if not canonical:
        try:
            detected = detect_current_page()
            canonical = detected.payload.get("page_key")
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Cannot detect current page: {exc}")

    if canonical not in _PAGE_FILL_HANDLERS:
        raise HTTPException(status_code=400, detail=f"No fill handler for page {canonical}")

    try:
        result = fill_and_continue(canonical, dossier)
        fill_payload = result.get("fill_payload") or {}
        filled = list(fill_payload.get("filled") or [])
        missing = list(fill_payload.get("missing") or [])
        raw_new_key = result.get("new_page_key")
        new_page_key = bundle_page_id(raw_new_key) if raw_new_key else None
        application_id = result.get("application_id") or _current_application_id()

        # Auto-save checkpoint on success
        if result.get("fill_ok"):
            try:
                existing = load_checkpoint(checkpoint_workspace())
                completed = list(existing.completed_pages) if existing else []
                if canonical not in completed:
                    completed.append(canonical)
                cp = FillCheckpoint(
                    case_id=dossier.case_id,
                    application_id=application_id or (existing.application_id if existing else None),
                    completed_pages=completed,
                    current_page_key=new_page_key or raw_new_key,
                )
                save_checkpoint(cp, checkpoint_workspace())
            except Exception:
                pass  # checkpoint save is best-effort, don't fail the fill

        log_page_fill(dossier.case_id, canonical, len(filled), len(missing),
                      application_id=application_id,
                      ok=bool(result.get("fill_ok")))

        return FillContinueResponse(
            ok=bool(result.get("fill_ok") and result.get("next_ok")),
            page_key=canonical,
            new_page_key=new_page_key,
            filled=filled,
            missing=missing,
            message=f"Filled {len(filled)} fields, {len(missing)} missing. Next page: {new_page_key or 'unknown'}",
            application_id=application_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/save-page")
def post_save_page():
    """Click the Save button on the current DS-160 page."""
    tabs = _check_cdp()
    if not tabs:
        raise HTTPException(status_code=503, detail="Chrome not reachable on CDP port")
    try:
        result = save_current_page()
        return {"ok": result.ok, "payload": result.payload}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "visa_agent.server:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8765")),
        reload=False,
        log_level="info",
    )
