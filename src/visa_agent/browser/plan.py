from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import json

from visa_agent.planner import ExecutionPlan, PlannedAction


PAGE_ORDER = [
    "personal_page_1",
    "personal_page_2",
    "travel_page",
    "travel_companions_page",
    "previous_us_travel_page",
    "address_phone_page",
    "passport_page",
    "us_contact_page",
    "work_education_present_page",
    "work_education_previous_page",
    "work_education_additional_page",
    "family_relatives_page",
    "family_spouse_page",
    "security_part1_page",
    "security_part2_page",
    "security_part3_page",
    "security_part4_page",
    "security_part5_page",
]

PAGE_SAVE_CHECKPOINTS = {
    "personal_page_1": "save_after_identity_page",
    "travel_page": "save_after_travel_page",
    "work_education_present_page": "save_after_employment_page",
    "security_part5_page": "save_before_security_page",
}


def _page_for_field(field_id: str) -> str:
    if field_id.startswith("identity."):
        if field_id in (
            "identity.other_nationality", "identity.permanent_resident_other_country",
            "identity.national_id_number", "identity.us_social_security_number",
            "identity.us_taxpayer_id_number",
        ):
            return "personal_page_2"
        return "personal_page_1"
    if field_id.startswith("passport."):
        return "passport_page"
    if field_id.startswith("travel_companions."):
        return "travel_companions_page"
    if field_id.startswith("previous_us_travel."):
        return "previous_us_travel_page"
    if field_id.startswith("travel."):
        return "travel_page"
    if field_id.startswith("address.") or field_id.startswith("phone.") or field_id.startswith("social."):
        return "address_phone_page"
    if field_id.startswith("employment."):
        if field_id.startswith("employment.previous_"):
            return "work_education_previous_page"
        if field_id.startswith("employment.school_") or field_id.startswith("employment.major_"):
            return "work_education_previous_page"
        if field_id in ("employment.other_education",):
            return "work_education_previous_page"
        if field_id.startswith("employment.languages") or field_id.startswith("employment.countries_"):
            return "work_education_additional_page"
        if field_id.startswith("employment.clan_") or field_id.startswith("employment.organization_"):
            return "work_education_additional_page"
        if field_id.startswith("employment.specialized_") or field_id.startswith("employment.military_"):
            return "work_education_additional_page"
        if field_id.startswith("employment.insurgent_"):
            return "work_education_additional_page"
        return "work_education_present_page"
    if field_id.startswith("family."):
        if field_id.startswith("family.spouse_"):
            return "family_spouse_page"
        return "family_relatives_page"
    if field_id.startswith("security."):
        return "security_part1_page"
    return "unmapped_page"


def _locator_key(field_id: str) -> str:
    return field_id.replace(".", "_")


@dataclass(frozen=True)
class BrowserInstruction:
    action_type: str
    field_id: str
    locator_key: str
    proposed_value: str | bool | None
    notes: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PageBatch:
    page_id: str
    fill: list[BrowserInstruction]
    review: list[BrowserInstruction]
    blocked: list[BrowserInstruction]
    save_checkpoint: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "page_id": self.page_id,
            "fill": [item.to_dict() for item in self.fill],
            "review": [item.to_dict() for item in self.review],
            "blocked": [item.to_dict() for item in self.blocked],
            "save_checkpoint": self.save_checkpoint,
        }


@dataclass(frozen=True)
class BrowserExecutionPlan:
    pages: list[PageBatch]
    hard_stops: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "pages": [page.to_dict() for page in self.pages],
            "hard_stops": self.hard_stops,
        }


def _to_instruction(action: PlannedAction) -> BrowserInstruction:
    return BrowserInstruction(
        action_type=action.action_type,
        field_id=action.field_id,
        locator_key=_locator_key(action.field_id),
        proposed_value=action.proposed_value,
        notes=action.notes,
    )


def compile_browser_execution_plan(execution_plan: ExecutionPlan) -> BrowserExecutionPlan:
    grouped_fill: dict[str, list[BrowserInstruction]] = defaultdict(list)
    grouped_review: dict[str, list[BrowserInstruction]] = defaultdict(list)
    grouped_blocked: dict[str, list[BrowserInstruction]] = defaultdict(list)

    for action in execution_plan.fill_actions:
        grouped_fill[_page_for_field(action.field_id)].append(_to_instruction(action))
    for action in execution_plan.review_actions:
        grouped_review[_page_for_field(action.field_id)].append(_to_instruction(action))
    for action in execution_plan.blocked_actions:
        grouped_blocked[_page_for_field(action.field_id)].append(_to_instruction(action))

    page_ids = [
        page_id
        for page_id in PAGE_ORDER
        if grouped_fill.get(page_id) or grouped_review.get(page_id) or grouped_blocked.get(page_id)
    ]
    if grouped_fill.get("unmapped_page") or grouped_review.get("unmapped_page") or grouped_blocked.get("unmapped_page"):
        page_ids.append("unmapped_page")

    pages = [
        PageBatch(
            page_id=page_id,
            fill=grouped_fill.get(page_id, []),
            review=grouped_review.get(page_id, []),
            blocked=grouped_blocked.get(page_id, []),
            save_checkpoint=PAGE_SAVE_CHECKPOINTS.get(page_id),
        )
        for page_id in page_ids
    ]
    return BrowserExecutionPlan(pages=pages, hard_stops=list(execution_plan.hard_stops))


def render_browser_execution_plan_json(plan: BrowserExecutionPlan) -> str:
    return json.dumps(plan.to_dict(), indent=2, ensure_ascii=False)
