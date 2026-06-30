from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from visa_agent.browser.cdp_client import CDPWebSocket, find_target_websocket_url
from visa_agent.browser.live_ceac import CAPTCHA_INPUT_ID, START_LINK_ID


@dataclass(frozen=True)
class VisibleControlResult:
    action: str
    ok: bool
    payload: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _runtime_eval(ws_url: str, expression: str) -> dict[str, object]:
    with CDPWebSocket(ws_url) as client:
        response = client.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
    if "error" in response:
        raise RuntimeError(str(response["error"]))
    result = response.get("result", {}).get("result", {})
    return {"type": result.get("type"), "value": result.get("value")}


def inspect_visible_ceac_state(port: int = 9222, url_substring: str = "ceac.state.gov/genniv") -> VisibleControlResult:
    ws_url = find_target_websocket_url(url_substring=url_substring, port=port)
    expression = (
        "(() => { "
        f"const captcha = document.querySelector({json.dumps(CAPTCHA_INPUT_ID)}); "
        f"const start = document.querySelector({json.dumps(START_LINK_ID)}); "
        "return ({"
        "url: location.href,"
        "title: document.title,"
        "captchaLength: (captcha?.value || '').trim().length,"
        "captchaFilled: ((captcha?.value || '').trim().length) > 0,"
        "startVisible: !!start"
        "});"
        "})()"
    )
    result = _runtime_eval(ws_url, expression)
    return VisibleControlResult(
        action="inspect_visible_ceac_state",
        ok=True,
        payload=dict(result.get("value") or {}),
    )


def fill_captcha_and_start(
    captcha_text: str,
    port: int = 9222,
    url_substring: str = "ceac.state.gov/genniv",
) -> VisibleControlResult:
    ws_url = find_target_websocket_url(url_substring=url_substring, port=port)
    expression = (
        "(() => { "
        f"const captcha = document.querySelector({json.dumps(CAPTCHA_INPUT_ID)}); "
        f"const start = document.querySelector({json.dumps(START_LINK_ID)}); "
        "if (!captcha) { return {status: 'CAPTCHA_INPUT_NOT_FOUND'}; } "
        "if (!start) { return {status: 'START_LINK_NOT_FOUND'}; } "
        f"captcha.value = {json.dumps(captcha_text)}; "
        "captcha.dispatchEvent(new Event('input', { bubbles: true })); "
        "captcha.dispatchEvent(new Event('change', { bubbles: true })); "
        "start.click(); "
        "return {status: 'START_CLICKED', url: location.href, title: document.title}; "
        "})()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    return VisibleControlResult(
        action="fill_captcha_and_start",
        ok=payload.get("status") == "START_CLICKED",
        payload=payload,
    )

