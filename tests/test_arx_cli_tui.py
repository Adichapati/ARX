from __future__ import annotations

import argparse
import importlib
import io
import sys
import unittest
from contextlib import redirect_stdout
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


class ArxCliTuiTests(unittest.TestCase):
    def _load(self):
        import scripts.arx_cli as arx_cli

        return importlib.reload(arx_cli)

    def _clear_textual_modules(self):
        for key in list(sys.modules.keys()):
            if key == 'textual' or key.startswith('textual.'):
                sys.modules.pop(key, None)

    def test_cmd_tui_delegates_to_scripts_arx_tui_runner(self):
        arx_cli = self._load()

        fake_mod = SimpleNamespace(run_tui=lambda: 7)
        with patch('importlib.import_module', return_value=fake_mod) as m:
            rc = arx_cli.cmd_tui(argparse.Namespace())

        self.assertEqual(rc, 7)
        m.assert_called_once_with('scripts.arx_tui')

    def test_cmd_tui_shows_install_hint_when_tui_module_missing(self):
        arx_cli = self._load()

        out = io.StringIO()
        with patch('importlib.import_module', side_effect=ModuleNotFoundError('scripts.arx_tui')):
            with redirect_stdout(out):
                rc = arx_cli.cmd_tui(argparse.Namespace())

        self.assertEqual(rc, 1)
        self.assertIn('TUI dependencies missing', out.getvalue())

    def test_arx_tui_run_tui_returns_1_when_textual_missing(self):
        self._clear_textual_modules()
        import scripts.arx_tui as arx_tui

        arx_tui = importlib.reload(arx_tui)
        real_import = importlib.import_module

        def fake_import(name: str, package=None):
            if name.startswith('textual'):
                raise ModuleNotFoundError(name)
            return real_import(name, package)

        out = io.StringIO()
        with patch('importlib.import_module', side_effect=fake_import):
            with redirect_stdout(out):
                rc = arx_tui.run_tui()

        self.assertEqual(rc, 1)
        self.assertIn('textual is not installed', out.getvalue())

    def test_arx_tui_run_tui_calls_textual_runner_when_available(self):
        self._clear_textual_modules()
        import scripts.arx_tui as arx_tui

        arx_tui = importlib.reload(arx_tui)
        fake_textual_app = ModuleType('textual.app')
        real_import = importlib.import_module

        def fake_import(name: str, package=None):
            if name == 'textual.app':
                return fake_textual_app
            return real_import(name, package)

        with patch.object(arx_tui, 'run_textual_app', return_value=0) as run_app:
            with patch('importlib.import_module', side_effect=fake_import):
                rc = arx_tui.run_tui()

        self.assertEqual(rc, 0)
        run_app.assert_called_once()

    def test_arx_tui_once_mode_prints_snapshot(self):
        import scripts.arx_tui as arx_tui

        arx_tui = importlib.reload(arx_tui)

        out = io.StringIO()
        with patch.object(arx_tui, '_render_banner_text', return_value='ARX'):
            with patch.object(
                arx_tui,
                '_snapshot',
                return_value=arx_tui.ServiceSnapshot(
                    dashboard_up=True,
                    minecraft_up=False,
                    ollama_up=True,
                    playit_up=False,
                    playit_enabled=False,
                    playit_url='not-set',
                    dashboard_addr='http://localhost:18890/',
                    minecraft_path='/tmp/mc',
                ),
            ):
                with redirect_stdout(out):
                    with patch('sys.argv', ['arx_tui.py', '--once']):
                        rc = arx_tui.main()

        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn('ARX', text)
        self.assertIn('Dashboard : UP', text)
        self.assertIn('Minecraft : DOWN', text)


if __name__ == '__main__':
    unittest.main()
