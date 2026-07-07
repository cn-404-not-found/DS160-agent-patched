from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from visa_agent.mapping import MappedField


@dataclass(frozen=True)
class PlannedAction:
    action_type: str
    field_id: str
    proposed_value: str | bool | None
    notes: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlan:
    fill_actions: list[PlannedAction]
    review_actions: list[PlannedAction]
    blocked_actions: list[PlannedAction]
    hard_stops: list[str]
    save_checkpoints: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "fill_actions": [action.to_dict() for action in self.fill_actions],
            "review_actions": [action.to_dict() for action in self.review_actions],
            "blocked_actions": [action.to_dict() for action in self.blocked_actions],
            "hard_stops": self.hard_stops,
            "save_checkpoints": self.save_checkpoints,
        }


def _to_action(action_type: str, field: MappedField) -> PlannedAction:
    return PlannedAction(
        action_type=action_type,
        field_id=field.field_id,
        proposed_value=field.proposed_value,
        notes=field.notes,
    )


def build_execution_plan(mapped_fields: list[MappedField]) -> ExecutionPlan:
    fill_actions = [_to_action("fill", field) for field in mapped_fields if field.status == "ready"]
    review_actions = [_to_action("review", field) for field in mapped_fields if field.status == "needs_review"]
    blocked_actions = [_to_action("block", field) for field in mapped_fields if field.status == "blocked"]

    save_checkpoints = [
        "save_after_identity_page",
        "save_after_travel_page",
        "save_after_employment_page",
        "save_before_security_page",
    ]
    hard_stops = [
        "stop_on_captcha",
        "stop_on_applicant_signature",
    ]
    if review_actions:
        hard_stops.append("stop_for_operator_review_queue")
    if blocked_actions:
        hard_stops.append("stop_for_missing_required_data")

    return ExecutionPlan(
        fill_actions=fill_actions,
        review_actions=review_actions,
        blocked_actions=blocked_actions,
        hard_stops=hard_stops,
        save_checkpoints=save_checkpoints,
    )


def render_execution_plan_json(plan: ExecutionPlan) -> str:
    return json.dumps(plan.to_dict(), indent=2, ensure_ascii=False)

