from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ArxTuiPolishTests(unittest.TestCase):
    def _load(self):
        import scripts.arx_tui as arx_tui

        return importlib.reload(arx_tui)

    def test_resolve_tui_theme_prefers_env(self):
        arx_tui = self._load()

        with patch.dict(os.environ, {'ARX_TUI_THEME': 'mono'}):
            self.assertEqual(arx_tui.resolve_tui_theme(), 'mono')

    def test_resolve_tui_theme_reads_state_when_env_missing(self):
        arx_tui = self._load()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'state').mkdir(parents=True, exist_ok=True)
            (root / 'state' / 'arx_ui.json').write_text(json.dumps({'theme': 'classic_dark'}), encoding='utf-8')

            with patch.object(arx_tui, 'ROOT', root):
                with patch.dict(os.environ, {}, clear=False):
                    if 'ARX_TUI_THEME' in os.environ:
                        del os.environ['ARX_TUI_THEME']
                    self.assertEqual(arx_tui.resolve_tui_theme(), 'classic_dark')

    def test_reduce_motion_enabled_true_via_env(self):
        arx_tui = self._load()

        with patch.dict(os.environ, {'ARX_REDUCE_MOTION': 'true'}):
            self.assertTrue(arx_tui.reduce_motion_enabled())

    def test_reduce_motion_enabled_from_state_motion_false(self):
        arx_tui = self._load()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'state').mkdir(parents=True, exist_ok=True)
            (root / 'state' / 'arx_ui.json').write_text(json.dumps({'motion': False}), encoding='utf-8')

            with patch.object(arx_tui, 'ROOT', root):
                with patch.dict(os.environ, {'ARX_REDUCE_MOTION': ''}):
                    self.assertTrue(arx_tui.reduce_motion_enabled())

    def test_next_tui_theme_cycles(self):
        arx_tui = self._load()

        self.assertEqual(arx_tui.next_tui_theme('neon_underground'), 'classic_dark')
        self.assertEqual(arx_tui.next_tui_theme('classic_dark'), 'mono')
        self.assertEqual(arx_tui.next_tui_theme('mono'), 'neon_underground')

    def test_build_tui_css_reduced_motion_omits_transitions(self):
        arx_tui = self._load()

        css = arx_tui.build_tui_css(theme='mono', reduced_motion=True)
        self.assertIn('#banner', css)
        self.assertIn('#logs-box', css)
        self.assertNotIn('transition:', css)

    def test_build_tui_css_non_reduced_motion_has_transitions(self):
        arx_tui = self._load()

        css = arx_tui.build_tui_css(theme='neon_underground', reduced_motion=False)
        self.assertIn('transition:', css)


if __name__ == '__main__':
    unittest.main()
