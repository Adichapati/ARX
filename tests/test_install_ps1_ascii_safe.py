from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallPs1AsciiSafeTests(unittest.TestCase):
    def test_install_ps1_contains_only_ascii_chars(self):
        raw = (ROOT / 'install.ps1').read_bytes()
        # ASCII-safe script avoids PowerShell 5.1 ANSI parsing corruption issues.
        self.assertTrue(all(b < 128 for b in raw), 'install.ps1 must be ASCII-only')


if __name__ == '__main__':
    unittest.main()
