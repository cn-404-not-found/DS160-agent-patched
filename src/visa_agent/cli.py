from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from visa_agent.browser.driver_adapter import (
    build_agent_browser_commands,
    render_agent_browser_script,
    render_driver_manifest_json,
)
from visa_agent.browser.playwright_adapter import (
    build_playwright_commands,
    render_playwright_manifest_json,
    render_playwright_script,
)
from visa_agent.browser.visible_browser import (
    build_visible_ceac_commands,
    build_visible_browser_status_commands,
    render_visible_browser_manifest,
    render_visible_browser_script,
    render_visible_browser_status_script,
)
from visa_agent.browser.ceac_start_flow import (
    generate_prepare_script,
    generate_resume_commands,
    generate_status_commands,
    render_prepare_script,
    render_resume_script,
    render_start_flow_manifest,
    render_status_script,
)
from visa_agent.browser.live_ceac import (
    generate_ceac_start_commands,
    render_live_commands_json,
    render_live_shell_script,
)
from visa_agent.browser.live_form_fill import detect_current_page, fill_current_supported_page
from visa_agent.browser.plan import (
    compile_browser_execution_plan,
    render_browser_execution_plan_json,
)
from visa_agent.browser.runtime import build_runtime_plan, render_runtime_plan_json
from visa_agent.draft_bundle import build_draft_bundle, export_draft_bundle_file
from visa_agent.encryption import (
    load_encrypted_dossier,
    save_encrypted_dossier,
)
from visa_agent.mapping import map_dossier_to_ds160, render_mapping_json
from visa_agent.planner import build_execution_plan, render_execution_plan_json
from visa_agent.schema import load_dossier


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a DS-160 mapping draft from a dossier JSON.")
    from visa_agent._paths import sample_data_dir

    parser.add_argument(
        "dossier_path",
        nargs="?",
        default=str(sample_data_dir() / "china_b1b2_sample.json"),
        help="Path to an applicant dossier JSON file.",
    )
    parser.add_argument(
        "--mode",
        choices=(
            "mapping",
            "plan",
            "browser-plan",
            "runtime-plan",
            "driver-manifest",
            "agent-browser-script",
            "playwright-manifest",
            "playwright-script",
            "visible-browser-manifest",
            "visible-browser-script",
            "visible-browser-status-manifest",
            "visible-browser-status-script",
            "live-start-manifest",
            "live-start-script",
            "live-prepare-manifest",
            "live-prepare-script",
            "live-start-status-manifest",
            "live-start-status-script",
            "live-start-resume-manifest",
            "live-start-resume-script",
            "inspect-visible-page",
            "assist-visible-page",
            "draft-bundle",
            "export-draft-bundle",
            "encrypt",
            "decrypt",
        ),
        default="mapping",
        help="Output raw mappings, planning layers, or driver-ready command artifacts.",
    )
    parser.add_argument(
        "--start-url",
        default="https://ceac.state.gov/genniv/",
        help="Start URL for generated browser driver commands.",
    )
    parser.add_argument(
        "--ceac-location",
        default="CHINA, SHANGHAI",
        help="Real CEAC location label for live-start command generation.",
    )
    parser.add_argument(
        "--captcha-text",
        default=None,
        help="Optional captcha text for live-start command generation.",
    )
    parser.add_argument(
        "--ceac-flow",
        choices=("start", "retrieve"),
        default="start",
        help="CEAC start-page flow for live command generation.",
    )
    parser.add_argument(
        "--visible-browser-profile",
        default=".visible-browser-profile",
        help="Profile directory for visible local Chrome launch.",
    )
    parser.add_argument(
        "--remote-debugging-port",
        type=int,
        default=9222,
        help="Remote debugging port for visible local Chrome launch.",
    )
    parser.add_argument(
        "--output",
        default="export/draft_bundle.js",
        help="Output path for exported local draft bundle assets.",
    )
    parser.add_argument(
        "--passphrase",
        default=None,
        help="Passphrase for encrypting or decrypting a dossier file.",
    )
    args = parser.parse_args()
    if args.mode == "encrypt":
        if not args.passphrase:
            print("Error: --passphrase is required for encrypt mode", file=sys.stderr)
            return 1
        if len(args.passphrase) < 8:
            print("Error: passphrase must be at least 8 characters", file=sys.stderr)
            return 1
        src = Path(args.dossier_path)
        text = src.read_text(encoding="utf-8")
        dest = Path(args.output) if args.output else src.with_suffix(".enc.json")
        save_encrypted_dossier(text, args.passphrase, dest)
        print(f"Encrypted: {dest}")
        return 0

    if args.mode == "decrypt":
        if not args.passphrase:
            print("Error: --passphrase is required for decrypt mode", file=sys.stderr)
            return 1
        src = Path(args.dossier_path)
        try:
            dossier_dict = load_encrypted_dossier(src, args.passphrase)
        except Exception as exc:
            print(f"Error: decryption failed - {exc}", file=sys.stderr)
            return 1
        dest = Path(args.output) if args.output else src.with_name(src.stem + "_decrypted.json" if src.name.endswith(".enc.json") else src.name + ".dec.json")
        dest.write_text(json.dumps(dossier_dict, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Decrypted: {dest}")
        return 0

    dossier = load_dossier(args.dossier_path)
    mapped_fields = map_dossier_to_ds160(dossier)
    if args.mode == "draft-bundle":
        print(json.dumps(build_draft_bundle(dossier), indent=2, ensure_ascii=False))
        return 0
    if args.mode == "export-draft-bundle":
        path = export_draft_bundle_file(args.dossier_path, args.output)
        print(str(path))
        return 0
    if args.mode == "inspect-visible-page":
        print(json.dumps(detect_current_page().to_dict(), indent=2, ensure_ascii=False))
        return 0
    if args.mode == "assist-visible-page":
        print(json.dumps(fill_current_supported_page(dossier).to_dict(), indent=2, ensure_ascii=False))
        return 0
    if args.mode == "mapping":
        print(render_mapping_json(mapped_fields))
        return 0
    execution_plan = build_execution_plan(mapped_fields)
    if args.mode == "plan":
        print(render_execution_plan_json(execution_plan))
        return 0
    browser_plan = compile_browser_execution_plan(execution_plan)
    if args.mode == "browser-plan":
        print(render_browser_execution_plan_json(browser_plan))
        return 0
    runtime_plan = build_runtime_plan(browser_plan)
    if args.mode == "runtime-plan":
        print(render_runtime_plan_json(runtime_plan))
        return 0
    driver_commands = build_agent_browser_commands(runtime_plan, args.start_url)
    if args.mode == "driver-manifest":
        print(render_driver_manifest_json(driver_commands))
        return 0
    if args.mode == "agent-browser-script":
        print(render_agent_browser_script(driver_commands))
        return 0
    playwright_commands = build_playwright_commands(runtime_plan, args.start_url)
    if args.mode == "playwright-manifest":
        print(render_playwright_manifest_json(playwright_commands))
        return 0
    if args.mode == "playwright-script":
        print(render_playwright_script(playwright_commands))
        return 0
    profile_dir = str(Path(args.visible_browser_profile).resolve())
    visible_commands = build_visible_ceac_commands(
        url=args.start_url,
        profile_dir=profile_dir,
        remote_debugging_port=args.remote_debugging_port,
    )
    if args.mode == "visible-browser-manifest":
        print(render_visible_browser_manifest(visible_commands))
        return 0
    if args.mode == "visible-browser-script":
        print(render_visible_browser_script(visible_commands))
        return 0
    visible_status_commands = build_visible_browser_status_commands(
        remote_debugging_port=args.remote_debugging_port,
        expected_url_substring="ceac.state.gov/genniv",
    )
    if args.mode == "visible-browser-status-manifest":
        print(render_visible_browser_manifest(visible_status_commands))
        return 0
    if args.mode == "visible-browser-status-script":
        print(
            render_visible_browser_status_script(
                remote_debugging_port=args.remote_debugging_port,
                expected_url_substring="ceac.state.gov/genniv",
            )
        )
        return 0
    live_commands = generate_ceac_start_commands(
        location_label=args.ceac_location,
        captcha_text=args.captcha_text,
        flow=args.ceac_flow,
    )
    if args.mode == "live-start-manifest":
        print(render_live_commands_json(live_commands))
        return 0
    if args.mode == "live-start-script":
        print(render_live_shell_script(live_commands))
        return 0
    if args.mode == "live-prepare-manifest":
        print(render_start_flow_manifest(generate_prepare_script(args.ceac_location)))
        return 0
    if args.mode == "live-prepare-script":
        print(render_prepare_script(args.ceac_location))
        return 0
    if args.mode == "live-start-status-manifest":
        print(render_start_flow_manifest(generate_status_commands()))
        return 0
    if args.mode == "live-start-status-script":
        print(render_status_script())
        return 0
    if args.mode == "live-start-resume-manifest":
        print(render_start_flow_manifest(generate_resume_commands()))
        return 0
    print(render_resume_script())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
