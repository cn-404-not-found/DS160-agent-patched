from __future__ import annotations

from pathlib import Path
import shutil
import stat
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / "scripts" / "install-deps.sh"
START_SH = ROOT / "scripts" / "start.sh"
STOP_SH = ROOT / "scripts" / "stop.sh"
INSTALL_PS1 = ROOT / "scripts" / "install-deps.ps1"
START_PS1 = ROOT / "scripts" / "start.ps1"
STOP_PS1 = ROOT / "scripts" / "stop.ps1"
BASH_SCRIPT_PATHS = [INSTALL_SH, START_SH, STOP_SH]
POWERSHELL_SCRIPT_PATHS = [INSTALL_PS1, START_PS1, STOP_PS1]
ALL_SCRIPT_PATHS = [*BASH_SCRIPT_PATHS, *POWERSHELL_SCRIPT_PATHS]


class StartScriptsTests(unittest.TestCase):
    def test_scripts_exist(self) -> None:
        for script_path in ALL_SCRIPT_PATHS:
            self.assertTrue(script_path.exists(), f"missing script: {script_path}")

    def test_bash_scripts_are_executable(self) -> None:
        for script_path in BASH_SCRIPT_PATHS:
            mode = script_path.stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR, f"script is not executable: {script_path}")

    def test_bash_scripts_have_valid_bash_syntax(self) -> None:
        for script_path in BASH_SCRIPT_PATHS:
            subprocess.run(["bash", "-n", str(script_path)], check=True, cwd=ROOT)

    def test_install_sh_mentions_requirements(self) -> None:
        result = subprocess.run(
            ["bash", str(INSTALL_SH), "--python", "python3"],
            check=False,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertIn("requirements.txt", INSTALL_SH.read_text(encoding="utf-8"))
        self.assertIn("fastapi", ROOT.joinpath("requirements.txt").read_text(encoding="utf-8"))
        self.assertIn("uvicorn", ROOT.joinpath("requirements.txt").read_text(encoding="utf-8"))

    def test_start_sh_supports_dry_run(self) -> None:
        result = subprocess.run(
            ["bash", str(START_SH), "--dry-run"],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertIn("visa_agent.server", result.stdout)
        self.assertIn("--remote-debugging-port=9222", result.stdout)
        self.assertIn("open landing page", result.stdout)

    def test_stop_sh_supports_dry_run(self) -> None:
        result = subprocess.run(
            ["bash", str(STOP_SH), "--dry-run"],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertIn("scripts/stop.sh", result.stdout)
        self.assertIn("127.0.0.1:8765", result.stdout)
        self.assertIn("--remote-debugging-port=9222", result.stdout)

    def test_windows_scripts_include_dry_run_support(self) -> None:
        self.assertIn("--python", INSTALL_PS1.read_text(encoding="utf-8"))
        self.assertIn("--dry-run", START_PS1.read_text(encoding="utf-8"))
        self.assertIn("--dry-run", STOP_PS1.read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh is required to execute PowerShell dry-run tests")
    def test_windows_scripts_support_dry_run_when_pwsh_is_available(self) -> None:
        start_result = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(START_PS1), "--dry-run"],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertIn("visa_agent.server", start_result.stdout)
        self.assertIn("--remote-debugging-port=9222", start_result.stdout)
        self.assertIn("open landing page", start_result.stdout)

        stop_result = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(STOP_PS1), "--dry-run"],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertIn("scripts/stop.ps1", stop_result.stdout)
        self.assertIn("127.0.0.1:8765", stop_result.stdout)


if __name__ == "__main__":
    unittest.main()
