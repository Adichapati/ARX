from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallPs1LauncherLineTests(unittest.TestCase):
    def test_launcher_lines_use_valid_powershell_string_construction(self):
        text = (ROOT / 'install.ps1').read_text(encoding='ascii')
        self.assertIn("('set \"ARX_PY={0}\"' -f $pythonPath)", text)
        self.assertIn("('set \"ARX_CLI={0}\"' -f $cliPath)", text)
        self.assertNotIn('"set \\\"ARX_PY=$pythonPath\\\"",', text)
        self.assertNotIn('"set \\\"ARX_CLI=$cliPath\\\"",', text)


if __name__ == '__main__':
    unittest.main()
