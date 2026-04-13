from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


class BuildRuntimeBundleTests(unittest.TestCase):
    def test_bundle_contains_fixed_installer_and_lean_contents(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "arx-runtime.zip"
            subprocess.run(
                ["python3", "scripts/build_runtime_bundle.py", "--output", str(out)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(out.exists(), "bundle should be created")
            self.assertLess(out.stat().st_size, 100 * 1024 * 1024, "bundle should stay under GitHub 100MB limit")

            with zipfile.ZipFile(out) as zf:
                names = set(zf.namelist())
                self.assertIn("install.ps1", names)
                self.assertIn("install.sh", names)
                self.assertIn("scripts/arx_cli.py", names)
                self.assertIn("dashboard/app.py", names)
                self.assertIn("prompts/gemma-minecraft-commands.md", names)
                self.assertNotIn("app/minecraft_server/server.jar", names)
                self.assertFalse(any(name.startswith("app/minecraft_server/libraries/") for name in names))
                self.assertFalse(any(name.startswith("app/minecraft_server/world/") for name in names))

                install_ps1 = zf.read("install.ps1").decode("utf-8", errors="replace")
                self.assertIn("$launcherLines = @(", install_ps1)
                self.assertNotIn("$launcher = @\"", install_ps1)


if __name__ == "__main__":
    unittest.main()
