from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from visa_agent.browser.locators import LocatorSpec, resolve_locator
from visa_agent.browser.plan import BrowserExecutionPlan, BrowserInstruction


@dataclass(frozen=True)
class ResolvedRuntimeInstruction:
    action_type: str
    field_id: str
    locator_key: str
    locator: dict[str, str] | None
    proposed_value: str | bool | None
    evidence_refs: list[str]
    notes: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PageRuntimePlan:
    page_id: str
    open_page: bool
    snapshot_before: bool
    fill_instructions: list[ResolvedRuntimeInstruction]
    review_instructions: list[ResolvedRuntimeInstruction]
    blocked_instructions: list[ResolvedRuntimeInstruction]
    save_checkpoint: str | None
    page_stops: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "page_id": self.page_id,
            "open_page": self.open_page,
            "snapshot_before": self.snapshot_before,
            "fill_instructions": [item.to_dict() for item in self.fill_instructions],
            "review_instructions": [item.to_dict() for item in self.review_instructions],
            "blocked_instructions": [item.to_dict() for item in self.blocked_instructions],
            "save_checkpoint": self.save_checkpoint,
            "page_stops": self.page_stops,
        }


@dataclass(frozen=True)
class RuntimePlan:
    pages: list[PageRuntimePlan]
    global_hard_stops: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "pages": [page.to_dict() for page in self.pages],
            "global_hard_stops": self.global_hard_stops,
        }


def _serialize_locator(locator: LocatorSpec | None) -> dict[str, str] | None:
    if locator is None:
        return None
    return locator.to_dict()


def _resolve_instruction(page_id: str, instruction: BrowserInstruction) -> ResolvedRuntimeInstruction:
    locator = resolve_locator(page_id, instruction.locator_key)
    return ResolvedRuntimeInstruction(
        action_type=instruction.action_type,
        field_id=instruction.field_id,
        locator_key=instruction.locator_key,
        locator=_serialize_locator(locator),
        proposed_value=instruction.proposed_value,
        evidence_refs=instruction.evidence_refs,
        notes=instruction.notes,
    )


def build_runtime_plan(browser_plan: BrowserExecutionPlan) -> RuntimePlan:
    pages: list[PageRuntimePlan] = []
    global_hard_stops = list(browser_plan.hard_stops)

    for page in browser_plan.pages:
        fill_instructions = [_resolve_instruction(page.page_id, item) for item in page.fill]
        review_instructions = [_resolve_instruction(page.page_id, item) for item in page.review]
        blocked_instructions = [_resolve_instruction(page.page_id, item) for item in page.blocked]

        page_stops: list[str] = []
        if review_instructions:
            page_stops.append("pause_for_review")
        if blocked_instructions:
            page_stops.append("pause_for_missing_data")

        missing_locator_instructions = [
            item
            for item in [*fill_instructions, *review_instructions, *blocked_instructions]
            if item.locator is None
        ]
        if missing_locator_instructions:
            page_stops.append("pause_for_missing_locator_binding")
            if "stop_for_missing_locator_binding" not in global_hard_stops:
                global_hard_stops.append("stop_for_missing_locator_binding")

        pages.append(
            PageRuntimePlan(
                page_id=page.page_id,
                open_page=True,
                snapshot_before=True,
                fill_instructions=fill_instructions,
                review_instructions=review_instructions,
                blocked_instructions=blocked_instructions,
                save_checkpoint=page.save_checkpoint,
                page_stops=page_stops,
            )
        )

    return RuntimePlan(pages=pages, global_hard_stops=global_hard_stops)


def render_runtime_plan_json(plan: RuntimePlan) -> str:
    return json.dumps(plan.to_dict(), indent=2, ensure_ascii=False)

