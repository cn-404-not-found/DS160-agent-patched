from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from visa_agent.browser.runtime import RuntimePlan, ResolvedRuntimeInstruction


@dataclass(frozen=True)
class PlaywrightCommand:
    operation: str
    page_id: str
    executable: bool
    command: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _js_value(value: str | bool | None) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False)


def _render_fill_instruction(page_id: str, instruction: ResolvedRuntimeInstruction) -> PlaywrightCommand:
    locator = instruction.locator or {}
    input_kind = locator.get("input_kind")
    target = str(locator.get("target", instruction.locator_key))
    value_expr = _js_value(instruction.proposed_value)
    target_expr = _js_string(target)

    if input_kind in {"text", "date"}:
        code = (
            "async page => { "
            f"await page.getByLabel({target_expr}, {{ exact: false }}).fill(String({value_expr} ?? '')); "
            "}"
        )
        return PlaywrightCommand(
            operation="fill_by_label",
            page_id=page_id,
            executable=True,
            command="npx --yes @playwright/cli run-code " + _shell_single_quote(code),
            notes=instruction.notes,
        )

    if input_kind == "select":
        code = (
            "async page => { "
            f"const label = {target_expr}; "
            f"const value = String({value_expr} ?? ''); "
            "const field = page.getByLabel(label, { exact: false }); "
            "await field.selectOption({ label: value }).catch(async () => { await field.selectOption(value); }); "
            "}"
        )
        return PlaywrightCommand(
            operation="select_by_label",
            page_id=page_id,
            executable=True,
            command="npx --yes @playwright/cli run-code " + _shell_single_quote(code),
            notes=instruction.notes,
        )

    if input_kind == "radio":
        choice_labels = locator.get("choice_labels") or {}
        choice = choice_labels.get("true" if bool(instruction.proposed_value) else "false", "Yes")
        code = (
            "async page => { "
            f"const question = {target_expr}; "
            f"const choice = {_js_string(choice)}; "
            "const questionNode = page.getByText(question, { exact: false }).first(); "
            "const container = questionNode.locator('xpath=ancestor::*[self::tr or self::fieldset or self::div][1]'); "
            "if (await container.getByLabel(choice, { exact: false }).count()) { "
            "  await container.getByLabel(choice, { exact: false }).first().check(); "
            "} else if (await container.getByText(choice, { exact: false }).count()) { "
            "  await container.getByText(choice, { exact: false }).first().click(); "
            "} else { "
            "  throw new Error(`Radio option not found for ${question} -> ${choice}`); "
            "} "
            "}"
        )
        return PlaywrightCommand(
            operation="radio_by_question",
            page_id=page_id,
            executable=True,
            command="npx --yes @playwright/cli run-code " + _shell_single_quote(code),
            notes=instruction.notes,
        )

    return PlaywrightCommand(
        operation="unsupported_binding",
        page_id=page_id,
        executable=False,
        command=f"# UNSUPPORTED {instruction.field_id}",
        notes="Unsupported runtime instruction kind.",
    )


def build_playwright_commands(runtime_plan: RuntimePlan, start_url: str) -> list[PlaywrightCommand]:
    commands: list[PlaywrightCommand] = [
        PlaywrightCommand(
            operation="open",
            page_id="session",
            executable=True,
            command=f"npx --yes @playwright/cli open {start_url}",
            notes="Open DS-160 session.",
        ),
        PlaywrightCommand(
            operation="wait_for_page",
            page_id="session",
            executable=True,
            command="npx --yes @playwright/cli run-code 'async page => { await page.locator(\"body\").waitFor(); }'",
            notes=None,
        ),
    ]

    for page in runtime_plan.pages:
        commands.append(
            PlaywrightCommand(
                operation="page_marker",
                page_id=page.page_id,
                executable=False,
                command=f"# PAGE {page.page_id}",
                notes=None,
            )
        )
        for instruction in page.fill_instructions:
            commands.append(_render_fill_instruction(page.page_id, instruction))
        for instruction in page.review_instructions:
            commands.append(
                PlaywrightCommand(
                    operation="pause_for_review",
                    page_id=page.page_id,
                    executable=False,
                    command=f"# REVIEW REQUIRED {instruction.field_id}: {instruction.notes or 'Operator review required.'}",
                    notes=None,
                )
            )
        for instruction in page.blocked_instructions:
            commands.append(
                PlaywrightCommand(
                    operation="pause_for_missing_data",
                    page_id=page.page_id,
                    executable=False,
                    command=f"# BLOCKED {instruction.field_id}: {instruction.notes or 'Missing required data.'}",
                    notes=None,
                )
            )
        if page.save_checkpoint:
            commands.append(
                PlaywrightCommand(
                    operation="save_checkpoint",
                    page_id=page.page_id,
                    executable=False,
                    command=f"# SAVE CHECKPOINT {page.save_checkpoint}",
                    notes="Bind to real save button after live page inspection.",
                )
            )
        commands.append(
            PlaywrightCommand(
                operation="continue_to_next_page",
                page_id=page.page_id,
                executable=False,
                command=f"# CONTINUE FROM {page.page_id}",
                notes="Continue-button locator still needs live form-page binding.",
            )
        )

    commands.append(
        PlaywrightCommand(
            operation="final_sign_checkpoint",
            page_id="final_review",
            executable=False,
            command="# FINAL SIGN CHECKPOINT",
            notes="Do not auto-click final sign until applicant review is complete.",
        )
    )
    return commands


def render_playwright_manifest_json(commands: list[PlaywrightCommand]) -> str:
    return json.dumps([command.to_dict() for command in commands], indent=2, ensure_ascii=False)


def render_playwright_script(commands: list[PlaywrightCommand]) -> str:
    return "\n".join(command.command for command in commands)

