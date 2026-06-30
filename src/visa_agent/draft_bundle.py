from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from visa_agent.browser.plan import compile_browser_execution_plan
from visa_agent.mapping import map_dossier_to_ds160
from visa_agent.planner import build_execution_plan
from visa_agent.schema import ApplicantDossier, load_dossier

TOP_STEPS = [
    {"id": "complete", "label": "COMPLETE"},
    {"id": "photo", "label": "PHOTO"},
    {"id": "review", "label": "REVIEW"},
    {"id": "sign", "label": "SIGN"},
]

FLOW_STRUCTURE = [
    {"section_id": "getting_started", "label": "Getting Started", "pages": [{"page_id": "getting_started", "label": "Getting Started"}]},
    {
        "section_id": "personal",
        "label": "Personal",
        "pages": [
            {"page_id": "personal_page_1", "label": "Personal 1"},
            {"page_id": "personal_page_2", "label": "Personal 2"},
        ],
    },
    {"section_id": "travel", "label": "Travel", "pages": [{"page_id": "travel_page", "label": "Travel"}]},
    {
        "section_id": "travel_companions",
        "label": "Travel Companions",
        "pages": [{"page_id": "travel_companions_page", "label": "Travel Companions"}],
    },
    {
        "section_id": "previous_us_travel",
        "label": "Previous U.S. Travel",
        "pages": [{"page_id": "previous_us_travel_page", "label": "Previous U.S. Travel"}],
    },
    {
        "section_id": "address_phone",
        "label": "Address and Phone",
        "pages": [{"page_id": "address_phone_page", "label": "Address and Phone"}],
    },
    {"section_id": "passport", "label": "Passport", "pages": [{"page_id": "passport_page", "label": "Passport"}]},
    {"section_id": "us_contact", "label": "U.S. Contact", "pages": [{"page_id": "us_contact_page", "label": "U.S. Contact"}]},
    {
        "section_id": "family",
        "label": "Family",
        "pages": [
            {"page_id": "family_relatives_page", "label": "Family: Relatives"},
            {"page_id": "family_spouse_page", "label": "Family: Spouse"},
        ],
    },
    {
        "section_id": "work_education_training",
        "label": "Work / Education / Training",
        "pages": [
            {"page_id": "work_education_present_page", "label": "Work / Education: Present"},
            {"page_id": "work_education_previous_page", "label": "Work / Education: Previous"},
            {"page_id": "work_education_additional_page", "label": "Work / Education: Additional"},
        ],
    },
    {
        "section_id": "security_background",
        "label": "Security and Background",
        "pages": [
            {"page_id": "security_part1_page", "label": "Security: Part 1"},
            {"page_id": "security_part2_page", "label": "Security: Part 2"},
            {"page_id": "security_part3_page", "label": "Security: Part 3"},
            {"page_id": "security_part4_page", "label": "Security: Part 4"},
            {"page_id": "security_part5_page", "label": "Security: Part 5"},
        ],
    },
]

PAGE_METADATA = {
    "getting_started": {
        "save_checkpoint": None,
        "fill": [],
        "review": [],
        "blocked": [],
        "autofill_count": 0,
        "review_count": 0,
        "blocked_count": 0,
        "status": "reference",
        "notes": ["入口页，不属于正式表单字段填写。"],
    },
    "personal_page_1": {"status": "implemented"},
    "personal_page_2": {"status": "implemented"},
    "travel_page": {"status": "implemented"},
    "travel_companions_page": {"status": "implemented"},
    "previous_us_travel_page": {"status": "implemented"},
    "address_phone_page": {"status": "implemented"},
    "passport_page": {"status": "implemented"},
    "us_contact_page": {"status": "implemented"},
    "family_relatives_page": {"status": "implemented"},
    "family_spouse_page": {"status": "implemented"},
    "work_education_present_page": {"status": "implemented"},
    "work_education_previous_page": {"status": "implemented"},
    "work_education_additional_page": {"status": "implemented"},
    "security_part1_page": {"status": "implemented"},
    "security_part2_page": {"status": "implemented"},
    "security_part3_page": {"status": "implemented"},
    "security_part4_page": {"status": "implemented"},
    "security_part5_page": {"status": "implemented"},
}


def _empty_page(page_id: str, label: str) -> dict[str, object]:
    meta = PAGE_METADATA.get(page_id, {})
    return {
        "page_id": page_id,
        "label": label,
        "save_checkpoint": meta.get("save_checkpoint"),
        "fill": list(meta.get("fill", [])),
        "review": list(meta.get("review", [])),
        "blocked": list(meta.get("blocked", [])),
        "autofill_count": int(meta.get("autofill_count", 0)),
        "review_count": int(meta.get("review_count", 0)),
        "blocked_count": int(meta.get("blocked_count", 0)),
        "status": str(meta.get("status", "planned")),
        "notes": list(meta.get("notes", [])),
    }


def build_draft_bundle(dossier: ApplicantDossier) -> dict[str, object]:
    mapped = map_dossier_to_ds160(dossier)
    execution_plan = build_execution_plan(mapped)
    browser_plan = compile_browser_execution_plan(execution_plan)

    status_counts = {"ready": 0, "needs_review": 0, "blocked": 0}
    for field in mapped:
        status_counts[field.status] = status_counts.get(field.status, 0) + 1

    resolved_pages = {}
    for page in browser_plan.pages:
        existing = PAGE_METADATA.get(page.page_id, {})
        resolved_pages[page.page_id] = {
            "page_id": page.page_id,
            "label": next(
                (
                    item["label"]
                    for section in FLOW_STRUCTURE
                    for item in section["pages"]
                    if item["page_id"] == page.page_id
                ),
                page.page_id,
            ),
            "save_checkpoint": page.save_checkpoint,
            "fill": [asdict(item) for item in page.fill],
            "review": [asdict(item) for item in page.review],
            "blocked": [asdict(item) for item in page.blocked],
            "autofill_count": len(page.fill),
            "review_count": len(page.review),
            "blocked_count": len(page.blocked),
            "status": existing.get("status", "implemented"),
            "notes": list(existing.get("notes", [])),
        }

    pages = []
    navigation = []
    for section in FLOW_STRUCTURE:
        nav_pages = []
        for item in section["pages"]:
            page = resolved_pages.get(item["page_id"], _empty_page(item["page_id"], item["label"]))
            pages.append(page)
            nav_pages.append(
                {
                    "page_id": page["page_id"],
                    "label": page["label"],
                    "status": page["status"],
                }
            )
        navigation.append(
            {
                "section_id": section["section_id"],
                "label": section["label"],
                "pages": nav_pages,
            }
        )

    return {
        "case_id": dossier.case_id,
        "summary": {
            "status_counts": status_counts,
            "page_count": len(pages),
            "hard_stops": execution_plan.hard_stops,
        },
        "top_steps": TOP_STEPS,
        "navigation": navigation,
        "pages": pages,
    }


def export_draft_bundle_file(
    dossier_path: str | Path,
    output_path: str | Path,
) -> Path:
    dossier = load_dossier(dossier_path)
    bundle = build_draft_bundle(dossier)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "window.DS160_DRAFT_BUNDLE = " + json.dumps(bundle, indent=2, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    return output
