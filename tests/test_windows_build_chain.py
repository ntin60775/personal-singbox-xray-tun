import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = REPO_ROOT / "build" / "windows"


class WindowsBuildChainTests(unittest.TestCase):
    def test_runtime_asset_manifest_pins_win81_assets(self) -> None:
        manifest = json.loads((BUILD_DIR / "runtime-assets.win81.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["target"], "windows-8.1-x64")
        self.assertEqual(manifest["xray"]["asset"], "Xray-win7-64.zip")
        self.assertNotIn("latest", manifest["xray"]["url"].lower())
        self.assertRegex(manifest["xray"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(manifest["wintun"]["asset"], "wintun-0.14.1.zip")
        self.assertRegex(manifest["wintun"]["sha256"], r"^[0-9a-f]{64}$")

    def test_build_script_rejects_unverified_fallback_policy(self) -> None:
        script = (BUILD_DIR / "build-win81-release.ps1").read_text(encoding="utf-8")

        self.assertNotIn("releases/latest", script)
        self.assertNotRegex(script, re.compile(r"windows-64.*fallback", re.IGNORECASE | re.DOTALL))
        self.assertIn("Assert-Sha256", script)
        self.assertIn("Offline-режим запрещает скачивание", script)

    def test_preflight_script_checks_python_dotnet_and_venv(self) -> None:
        script = (BUILD_DIR / "install-win81-build-deps.ps1").read_text(encoding="utf-8")

        self.assertIn("Assert-Python", script)
        self.assertIn("Assert-DotNet48", script)
        self.assertIn(".venv-win81-x64", script)
        self.assertIn("python-build-requirements.txt", script)

    def test_windows_build_docs_are_linked_to_current_task(self) -> None:
        docs = (REPO_ROOT / "docs" / "windows" / "README-win81-build.md").read_text(encoding="utf-8")

        self.assertIn("TASK-2026-0058", docs)
        self.assertIn("-StageRuntimeOnly", docs)
        self.assertIn("-Offline", docs)


if __name__ == "__main__":
    unittest.main()
