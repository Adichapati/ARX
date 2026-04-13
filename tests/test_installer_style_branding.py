from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerStyleBrandingTests(unittest.TestCase):
    def test_install_sh_has_style_resolution_and_assets(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8", errors="ignore")

        self.assertIn("resolve_installer_style()", text)
        self.assertIn("installer_state_style()", text)
        self.assertIn("supports_unicode()", text)
        self.assertIn("ARX_STYLE", text)
        self.assertIn("state/arx_ui.json", text)
        self.assertIn('underground|classic|dos|minimal|off', text)
        self.assertIn('█████╗ ██████╗ ██╗  ██╗', text)
        self.assertIn('______   ______  __   __', text)

    def test_install_ps1_has_style_resolution_and_assets(self):
        text = (ROOT / "install.ps1").read_text(encoding="utf-8", errors="ignore")

        self.assertIn("function Resolve-InstallerStyle", text)
        self.assertIn("function Get-StateStyle", text)
        self.assertIn("function Test-UnicodeSupport", text)
        self.assertIn("ARX_STYLE", text)
        self.assertIn("state\\arx_ui.json", text)
        self.assertIn("underground", text)
        self.assertIn("dos", text)
        self.assertIn("minimal", text)
        self.assertIn("off", text)
        # Keep Windows banner ASCII-safe to avoid encoding parse failures in PS 5.1 bootstrap mode.
        self.assertIn("    ___    ____  _  __", text)
        self.assertIn("______   ______  __   __", text)


if __name__ == "__main__":
    unittest.main()
