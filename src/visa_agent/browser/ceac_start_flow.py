from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from visa_agent.browser.live_ceac import (
    CAPTCHA_INPUT_ID,
    LOCATION_SELECT_ID,
    START_LINK_ID,
    generate_ceac_start_commands,
)


def _shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


@dataclass(frozen=True)
class StartFlowCommand:
    step: str
    executable: bool
    command: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_prepare_script(location_label: str) -> list[StartFlowCommand]:
    commands = generate_ceac_start_commands(location_label=location_label)
    return [
        StartFlowCommand(step=item.step, executable=item.executable, command=item.command, notes=item.notes)
        for item in commands[:3]
    ]


def generate_status_commands() -> list[StartFlowCommand]:
    return [
        StartFlowCommand(
            step="read_start_page_status",
            executable=True,
            command=(
                "npx --yes @playwright/cli eval "
                + _shell_single_quote(
                    "(() => { "
                    f"const location = document.querySelector({json.dumps(LOCATION_SELECT_ID)}); "
                    f"const captcha = document.querySelector({json.dumps(CAPTCHA_INPUT_ID)}); "
                    f"const start = document.querySelector({json.dumps(START_LINK_ID)}); "
                    "return JSON.stringify({"
                    "locationValue: location?.value || null,"
                    "locationText: location?.selectedOptions?.[0]?.textContent?.trim() || null,"
                    "captchaLength: (captcha?.value || '').trim().length,"
                    "captchaFilled: ((captcha?.value || '').trim().length) > 0,"
                    "startVisible: !!start"
                    "});"
                    "})()"
                )
            ),
            notes="Probe whether the CEAC start page is prepared for a resume click.",
        )
    ]


def generate_resume_commands() -> list[StartFlowCommand]:
    return [
        StartFlowCommand(
            step="click_start_if_ready",
            executable=True,
            command=(
                "npx --yes @playwright/cli run-code "
                + _shell_single_quote(
                    "async page => { "
                    f"const captcha = page.locator({json.dumps(CAPTCHA_INPUT_ID)}); "
                    "const value = (await captcha.inputValue()).trim(); "
                    "if (!value) { return 'CAPTCHA_EMPTY'; } "
                    f"await page.locator({json.dumps(START_LINK_ID)}).click(); "
                    "return 'START_CLICKED'; "
                    "}"
                )
            ),
            notes="Will not click start unless captcha text is already present in the live page.",
        )
    ]


def render_start_flow_manifest(commands: list[StartFlowCommand]) -> str:
    return json.dumps([command.to_dict() for command in commands], indent=2, ensure_ascii=False)


def render_start_flow_script(commands: list[StartFlowCommand]) -> str:
    return "\n".join(command.command for command in commands)


def render_prepare_script(location_label: str) -> str:
    return render_start_flow_script(generate_prepare_script(location_label))


def render_status_script() -> str:
    return render_start_flow_script(generate_status_commands())


def render_resume_script() -> str:
    return render_start_flow_script(generate_resume_commands())

