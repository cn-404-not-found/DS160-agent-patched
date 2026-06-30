from __future__ import annotations

from dataclasses import asdict, dataclass
import json


LOCATION_SELECT_ID = "#ctl00_SiteContentPlaceHolder_ucLocation_ddlLocation"
CAPTCHA_INPUT_ID = "#ctl00_SiteContentPlaceHolder_ucLocation_IdentifyCaptcha1_txtCodeTextBox"
START_LINK_ID = "#ctl00_SiteContentPlaceHolder_lnkNew"
RETRIEVE_LINK_ID = "#ctl00_SiteContentPlaceHolder_lnkRetrieve"


def _js_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


@dataclass(frozen=True)
class LiveCommand:
    step: str
    executable: bool
    command: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_ceac_start_commands(
    location_label: str,
    captcha_text: str | None = None,
    flow: str = "start",
) -> list[LiveCommand]:
    if flow not in {"start", "retrieve"}:
        raise ValueError("flow must be either 'start' or 'retrieve'")

    commands: list[LiveCommand] = [
        LiveCommand(
            step="open_ceac",
            executable=True,
            command="npx --yes @playwright/cli open https://ceac.state.gov/genniv/",
            notes="Open the official CEAC DS-160 instructions page.",
        ),
        LiveCommand(
            step="wait_for_page",
            executable=True,
            command="npx --yes @playwright/cli run-code 'async page => { await page.locator(\"body\").waitFor(); }'",
            notes=None,
        ),
        LiveCommand(
            step="select_location",
            executable=True,
            command="npx --yes @playwright/cli run-code "
            + _shell_single_quote(
                "async page => { "
                f"await page.locator({ _js_quote(LOCATION_SELECT_ID) }).selectOption({{ label: {_js_quote(location_label)} }}); "
                f"return await page.locator({ _js_quote(LOCATION_SELECT_ID) }).inputValue(); "
                "}"
            ),
            notes="Select the consular location on the real CEAC page.",
        ),
    ]

    if captcha_text is None:
        commands.append(
            LiveCommand(
                step="captcha_required",
                executable=False,
                command=f"# Fill captcha into {CAPTCHA_INPUT_ID} before continuing.",
                notes="Captcha must be completed by a human or a separately approved input step.",
            )
        )
    else:
        commands.append(
            LiveCommand(
                step="fill_captcha",
                executable=True,
                command="npx --yes @playwright/cli run-code "
                + _shell_single_quote(
                    "async page => { "
                    f"await page.locator({ _js_quote(CAPTCHA_INPUT_ID) }).fill({_js_quote(captcha_text)}); "
                    "}"
                ),
                notes="Uses the provided captcha text verbatim.",
            )
        )

    target_id = START_LINK_ID if flow == "start" else RETRIEVE_LINK_ID
    target_name = "start_application" if flow == "start" else "retrieve_application"
    if captcha_text is None:
        commands.append(
            LiveCommand(
                step=target_name,
                executable=False,
                command=f"# Click {target_id} after captcha is filled.",
                notes="Blocked pending human captcha completion.",
            )
        )
    else:
        commands.append(
            LiveCommand(
                step=target_name,
                executable=True,
                command="npx --yes @playwright/cli run-code "
                + _shell_single_quote(
                    "async page => { "
                    f"await page.locator({ _js_quote(target_id) }).click(); "
                    "}"
                ),
                notes="Clicks the selected CEAC flow entry point.",
            )
        )

    return commands


def render_live_commands_json(commands: list[LiveCommand]) -> str:
    return json.dumps([command.to_dict() for command in commands], indent=2, ensure_ascii=False)


def render_live_shell_script(commands: list[LiveCommand]) -> str:
    return "\n".join(command.command for command in commands)
