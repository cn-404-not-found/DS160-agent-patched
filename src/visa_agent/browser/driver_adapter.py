from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from visa_agent.browser.runtime import RuntimePlan, ResolvedRuntimeInstruction


@dataclass(frozen=True)
class DriverCommand:
    tool: str
    operation: str
    page_id: str
    executable: bool
    command: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _stringify_value(value: str | bool | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return value


def _render_agent_browser_fill(page_id: str, instruction: ResolvedRuntimeInstruction) -> DriverCommand:
    locator = instruction.locator or {}
    input_kind = locator.get("input_kind")
    target = locator.get("target", instruction.locator_key)
    value = _stringify_value(instruction.proposed_value)

    if input_kind in {"text", "date"}:
        command = f"agent-browser find label {_shell_quote(target)} fill {_shell_quote(value)}"
        return DriverCommand(
            tool="agent-browser",
            operation="fill_by_label",
            page_id=page_id,
            executable=True,
            command=command,
            notes=instruction.notes,
        )

    if input_kind == "select":
        return DriverCommand(
            tool="agent-browser",
            operation="select_by_label",
            page_id=page_id,
            executable=False,
            command=f"# SELECT label {target!r} -> {value!r}",
            notes="Selection by label is not yet bound to a concrete agent-browser command in this prototype.",
        )

    if input_kind == "radio":
        return DriverCommand(
            tool="agent-browser",
            operation="radio_by_label",
            page_id=page_id,
            executable=False,
            command=f"# RADIO label {target!r} -> {value!r}",
            notes="Radio handling still needs concrete DS-160 locator confirmation.",
        )

    return DriverCommand(
        tool="agent-browser",
        operation="unknown_locator_binding",
        page_id=page_id,
        executable=False,
        command=f"# UNKNOWN input kind for {instruction.field_id}",
        notes="Unsupported locator binding type.",
    )


def build_agent_browser_commands(runtime_plan: RuntimePlan, start_url: str) -> list[DriverCommand]:
    commands: list[DriverCommand] = [
        DriverCommand(
            tool="agent-browser",
            operation="open",
            page_id="session",
            executable=True,
            command=f"agent-browser open {_shell_quote(start_url)}",
            notes="Start DS-160 browser session.",
        ),
        DriverCommand(
            tool="agent-browser",
            operation="wait_load",
            page_id="session",
            executable=True,
            command="agent-browser wait --load networkidle",
            notes=None,
        ),
    ]

    for page in runtime_plan.pages:
        commands.append(
            DriverCommand(
                tool="agent-browser",
                operation="page_marker",
                page_id=page.page_id,
                executable=False,
                command=f"# PAGE {page.page_id}",
                notes=None,
            )
        )
        if page.snapshot_before:
            commands.append(
                DriverCommand(
                    tool="agent-browser",
                    operation="snapshot",
                    page_id=page.page_id,
                    executable=True,
                    command="agent-browser snapshot -i",
                    notes="Refresh interactive refs before acting on the page.",
                )
            )
        for instruction in page.fill_instructions:
            commands.append(_render_agent_browser_fill(page.page_id, instruction))
        for instruction in page.review_instructions:
            commands.append(
                DriverCommand(
                    tool="agent-browser",
                    operation="pause_for_review",
                    page_id=page.page_id,
                    executable=False,
                    command=f"# REVIEW REQUIRED {instruction.field_id}: {instruction.notes or 'Operator confirmation required.'}",
                    notes=None,
                )
            )
        for instruction in page.blocked_instructions:
            commands.append(
                DriverCommand(
                    tool="agent-browser",
                    operation="pause_for_missing_data",
                    page_id=page.page_id,
                    executable=False,
                    command=f"# BLOCKED {instruction.field_id}: {instruction.notes or 'Missing required data.'}",
                    notes=None,
                )
            )
        if page.save_checkpoint:
            commands.append(
                DriverCommand(
                    tool="agent-browser",
                    operation="save_checkpoint",
                    page_id=page.page_id,
                    executable=False,
                    command=f"# SAVE CHECKPOINT {page.save_checkpoint}",
                    notes="Bind this to the concrete DS-160 save action when page locators are finalized.",
                )
            )

    for stop in runtime_plan.global_hard_stops:
        commands.append(
            DriverCommand(
                tool="agent-browser",
                operation="hard_stop",
                page_id="global",
                executable=False,
                command=f"# HARD STOP {stop}",
                notes=None,
            )
        )
    return commands


def render_driver_manifest_json(commands: list[DriverCommand]) -> str:
    return json.dumps([command.to_dict() for command in commands], indent=2, ensure_ascii=False)


def render_agent_browser_script(commands: list[DriverCommand]) -> str:
    return "\n".join(command.command for command in commands)

