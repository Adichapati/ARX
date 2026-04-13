from __future__ import annotations

import importlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


class ArxCliStyleTests(unittest.TestCase):
    def _load(self):
        import scripts.arx_cli as arx_cli

        return importlib.reload(arx_cli)

    def test_style_set_persists_and_status_reports_value(self):
        arx_cli = self._load()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            state_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(arx_cli, "ROOT", root), patch.object(arx_cli, "STATE_DIR", state_dir):
                rc = arx_cli.cmd_style(arx_cli.argparse.Namespace(action="set", name="minimal"))
                self.assertEqual(rc, 0)

                data = json.loads((state_dir / "arx_ui.json").read_text(encoding="utf-8"))
                self.assertEqual(data.get("style"), "minimal")

                out = io.StringIO()
                with redirect_stdout(out):
                    rc2 = arx_cli.cmd_style(arx_cli.argparse.Namespace(action="status", name=None))
                self.assertEqual(rc2, 0)
                self.assertIn("style: minimal", out.getvalue())

    def test_help_prints_logo_when_style_enabled(self):
        arx_cli = self._load()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "arx_ui.json").write_text('{"style":"minimal"}', encoding="utf-8")

            with patch.object(arx_cli, "ROOT", root), patch.object(arx_cli, "STATE_DIR", state_dir):
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = arx_cli.cmd_help(arx_cli.argparse.Namespace())
                self.assertEqual(rc, 0)
                text = out.getvalue()
                self.assertIn("ARX command help", text)
                self.assertIn("___", text)


if __name__ == "__main__":
    unittest.main()
