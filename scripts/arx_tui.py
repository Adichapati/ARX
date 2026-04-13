#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import argparse
import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import psutil

try:
    from scripts.ui.style_engine import resolve_style, style_pack
except Exception:  # pragma: no cover
    from ui.style_engine import resolve_style, style_pack


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'
TUI_THEMES = ('neon_underground', 'classic_dark', 'mono')


_THEME_PALETTES: dict[str, dict[str, str]] = {
    'neon_underground': {
        'screen_bg': '#0b0f14',
        'right_border': '#2f3b4a',
        'banner': '#6ee7ff',
        'services': '#d1f7ff',
        'hotkeys': '#9ca3af',
        'logs_title': '#f9d65c',
        'modal_border': '#4c7aaf',
        'modal_bg': '#111827',
        'cmd_title': '#93c5fd',
    },
    'classic_dark': {
        'screen_bg': '#111111',
        'right_border': '#3a3a3a',
        'banner': '#70d6ff',
        'services': '#f0f0f0',
        'hotkeys': '#bdbdbd',
        'logs_title': '#ffdd57',
        'modal_border': '#5c7a99',
        'modal_bg': '#1a1a1a',
        'cmd_title': '#9ecbff',
    },
    'mono': {
        'screen_bg': '#0f0f0f',
        'right_border': '#4a4a4a',
        'banner': '#d4d4d4',
        'services': '#efefef',
        'hotkeys': '#bfbfbf',
        'logs_title': '#e0e0e0',
        'modal_border': '#8a8a8a',
        'modal_bg': '#151515',
        'cmd_title': '#f0f0f0',
    },
}


def _env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_PATH.exists():
        return out
    for raw in ENV_PATH.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = v.strip()
    return out


def cfg(key: str, default: str) -> str:
    env = os.environ.get(key)
    if env is not None and str(env).strip() != '':
        return str(env)
    return _env_file().get(key, default)


def bind_host() -> str:
    return cfg('BIND_HOST', '127.0.0.1')


def bind_port() -> int:
    try:
        return int(cfg('BIND_PORT', '18890'))
    except Exception:
        return 18890


def minecraft_dir() -> Path:
    return Path(cfg('MINECRAFT_DIR', str((ROOT / 'app' / 'minecraft_server').resolve()))).resolve()


def playit_enabled() -> bool:
    return cfg('PLAYIT_ENABLED', 'false').strip().lower() == 'true'


def playit_url() -> str:
    return cfg('PLAYIT_URL', '').strip()


def _port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _find_dashboard_procs() -> list[psutil.Process]:
    procs: list[psutil.Process] = []
    marker = str(ROOT)
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            cmd = ' '.join(proc.info.get('cmdline') or [])
            cwd = str(proc.info.get('cwd') or '')
            if 'uvicorn' in cmd and 'main:app' in cmd and (marker in cmd or marker in cwd):
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs


def _find_server_procs() -> list[psutil.Process]:
    procs: list[psutil.Process] = []
    marker = str(minecraft_dir())
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmd = ' '.join(proc.info.get('cmdline') or [])
            if 'java' in name and 'server.jar' in cmd and marker in cmd:
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs


def _find_ollama_procs() -> list[psutil.Process]:
    procs: list[psutil.Process] = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmd = ' '.join(proc.info.get('cmdline') or []).lower()
            if 'ollama' in name or 'ollama' in cmd:
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs


def _playit_running() -> bool:
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmd = ' '.join(proc.info.get('cmdline') or []).lower()
            if 'playit' in name or 'playit' in cmd:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _ollama_ok() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=0.8) as r:
            return r.status == 200
    except Exception:
        return False


def _tail(path: Path, lines: int = 8) -> str:
    if not path.exists():
        return '(log missing)'
    data = path.read_text(encoding='utf-8', errors='replace').splitlines()
    if not data:
        return '(empty log)'
    return '\n'.join(data[-lines:])


def _ui_state() -> dict:
    p = ROOT / 'state' / 'arx_ui.json'
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding='utf-8', errors='ignore'))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_ui_state(patch_obj: dict) -> None:
    p = ROOT / 'state' / 'arx_ui.json'
    data = _ui_state()
    data.update(patch_obj)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding='utf-8')


def resolve_tui_theme() -> str:
    env_theme = os.environ.get('ARX_TUI_THEME', '').strip().lower()
    if env_theme in TUI_THEMES:
        return env_theme

    state_theme = str(_ui_state().get('theme', '')).strip().lower()
    if state_theme in TUI_THEMES:
        return state_theme

    return 'neon_underground'


def reduce_motion_enabled() -> bool:
    env = os.environ.get('ARX_REDUCE_MOTION', '').strip().lower()
    if env in {'1', 'true', 'yes', 'on'}:
        return True

    state_motion = _ui_state().get('motion', True)
    if isinstance(state_motion, bool):
        return not state_motion
    return False


def next_tui_theme(current: str) -> str:
    c = (current or '').strip().lower()
    if c not in TUI_THEMES:
        return TUI_THEMES[0]
    idx = TUI_THEMES.index(c)
    return TUI_THEMES[(idx + 1) % len(TUI_THEMES)]


def build_tui_css(theme: str, reduced_motion: bool) -> str:
    palette = _THEME_PALETTES.get(theme, _THEME_PALETTES['neon_underground'])
    transition = '' if reduced_motion else '        transition: color 120ms, background 120ms;\n'
    return f"""
        Screen {{ background: {palette['screen_bg']}; }}
        #layout {{ height: 1fr; }}
        #left {{ width: 2fr; padding: 1 2; }}
        #right {{ width: 1fr; padding: 1 1; border-left: solid {palette['right_border']}; }}
        #banner {{ color: {palette['banner']}; }}
        #services {{ margin-top: 1; color: {palette['services']};{transition} }}
        #hotkeys {{ margin-top: 1; color: {palette['hotkeys']}; }}
        #logs-title {{ color: {palette['logs_title']}; }}
        #logs-box {{ height: 1fr; }}
        #cmd-modal {{
            width: 80%;
            height: 70%;
            margin: 2 4;
            border: round {palette['modal_border']};
            padding: 1;
            background: {palette['modal_bg']};
        }}
        #cmd-title {{ color: {palette['cmd_title']}; }}
        #cmd-log {{ height: 1fr; margin-top: 1; }}
        #theme-chip {{ color: {palette['logs_title']}; margin-top: 1; }}
    """


def _log_snippet(source: str) -> str:
    source = (source or 'dashboard').strip().lower()
    if source == 'dashboard':
        path = ROOT / 'state' / 'dashboard.log'
    elif source == 'server':
        path = minecraft_dir() / 'logs' / 'latest.log'
    elif source == 'ollama':
        p1 = ROOT / 'state' / 'ollama.log'
        p2 = Path('/tmp/arx-ollama.log')
        path = p1 if p1.exists() else p2
    elif source == 'playit':
        path = ROOT / 'state' / 'playit.log'
    else:
        return 'unknown log source'
    return _tail(path, lines=8)


@dataclass
class ServiceSnapshot:
    dashboard_up: bool
    minecraft_up: bool
    ollama_up: bool
    playit_up: bool
    playit_enabled: bool
    playit_url: str
    dashboard_addr: str
    minecraft_path: str


def _snapshot() -> ServiceSnapshot:
    host = bind_host()
    port = bind_port()
    dashboard_up = bool(_find_dashboard_procs() or _port_open(host, port))
    minecraft_up = bool(_find_server_procs())
    ollama_up = bool(_find_ollama_procs() or _ollama_ok())
    playit_up = _playit_running()

    return ServiceSnapshot(
        dashboard_up=dashboard_up,
        minecraft_up=minecraft_up,
        ollama_up=ollama_up,
        playit_up=playit_up,
        playit_enabled=playit_enabled(),
        playit_url=playit_url() or 'not-set',
        dashboard_addr=f'http://localhost:{port}/',
        minecraft_path=str(minecraft_dir()),
    )


def _run_arx_cli_command(*args: str) -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / 'scripts' / 'arx_cli.py'), *args]
    cp = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (cp.stdout or '').rstrip()
    err = (cp.stderr or '').rstrip()
    if err:
        out = (out + '\n' + err).strip() if out else err
    return cp.returncode, out


def _render_services_text(s: ServiceSnapshot) -> str:
    def mark(v: bool) -> str:
        return 'UP' if v else 'DOWN'

    return '\n'.join(
        [
            f'Dashboard : {mark(s.dashboard_up)}  ({s.dashboard_addr})',
            f'Minecraft : {mark(s.minecraft_up)}  ({s.minecraft_path})',
            f'Ollama    : {mark(s.ollama_up)}  (http://127.0.0.1:11434)',
            f'Playit    : {mark(s.playit_up)}  (enabled={str(s.playit_enabled).lower()}, url={s.playit_url})',
        ]
    )


def _render_banner_text() -> str:
    style_name = resolve_style(ROOT)
    pack = style_pack(ROOT, explicit=style_name)
    return pack.arx_logo or 'ARX'


def run_textual_app(theme: str, reduced_motion: bool) -> int:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Header, Static, TextLog

    initial_theme = theme if theme in TUI_THEMES else 'neon_underground'
    initial_reduced = bool(reduced_motion)

    class CommandResultScreen(ModalScreen[None]):
        BINDINGS = [Binding('escape', 'dismiss', 'Close')]

        def __init__(self, title: str, body: str) -> None:
            super().__init__()
            self._title = title
            self._body = body

        def compose(self) -> ComposeResult:
            yield Container(
                Static(f'{self._title} · Press Esc to close', id='cmd-title'),
                TextLog(id='cmd-log', wrap=True, highlight=False),
                id='cmd-modal',
            )

        def on_mount(self) -> None:
            log = self.query_one('#cmd-log', TextLog)
            for line in (self._body or '(no output)').splitlines() or ['(no output)']:
                log.write(line)

        def action_dismiss(self) -> None:
            self.dismiss(None)

    class ArxTuiApp(App):
        CSS = build_tui_css(initial_theme, initial_reduced)

        BINDINGS = [
            Binding('q', 'quit', 'Quit'),
            Binding('s', 'start_all', 'Start all'),
            Binding('x', 'stop_all', 'Stop'),
            Binding('r', 'restart_all', 'Restart'),
            Binding('o', 'open_dashboard', 'Open'),
            Binding('d', 'doctor', 'Doctor'),
            Binding('1', 'log_dashboard', 'Dash log'),
            Binding('2', 'log_server', 'Server log'),
            Binding('3', 'log_ollama', 'Ollama log'),
            Binding('4', 'log_playit', 'Playit log'),
            Binding('t', 'cycle_theme', 'Theme'),
            Binding('m', 'toggle_motion', 'Motion'),
        ]

        log_source = reactive('dashboard')
        current_theme = reactive(initial_theme)
        reduced_motion = reactive(initial_reduced)

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id='layout'):
                with Container(id='left'):
                    yield Static(_render_banner_text(), id='banner')
                    yield Static('', id='services')
                    yield Static('', id='theme-chip')
                    yield Static(
                        'Hotkeys: [s]start [x]stop [r]restart [o]open [d]doctor [1-4]logs [t]theme [m]motion [q]quit',
                        id='hotkeys',
                    )
                with Container(id='right'):
                    yield Static('', id='logs-title')
                    yield TextLog(id='logs-box', wrap=True, highlight=False)
            yield Footer()

        def on_mount(self) -> None:
            self.title = 'ARX TUI'
            self.sub_title = 'Agentic Runtime for eXecution'
            self.set_interval(1.6 if self.reduced_motion else 1.0, self.refresh_snapshot)
            self.refresh_snapshot()

        def _update_labels(self) -> None:
            self.query_one('#logs-title', Static).update(
                f'Logs · {self.log_source.upper()} · switch with 1/2/3/4'
            )
            motion_label = 'reduced' if self.reduced_motion else 'full'
            self.query_one('#theme-chip', Static).update(
                f'Theme: {self.current_theme} · Motion: {motion_label}'
            )

        def refresh_snapshot(self) -> None:
            snap = _snapshot()
            self.query_one('#services', Static).update(_render_services_text(snap))
            self._update_labels()

            log_widget = self.query_one('#logs-box', TextLog)
            log_widget.clear()
            for line in _log_snippet(self.log_source).splitlines():
                log_widget.write(line)

        def _run_action(self, title: str, *argv: str) -> None:
            rc, out = _run_arx_cli_command(*argv)
            cmd_str = ' '.join(argv)
            body = f"$ arx {cmd_str}\nexit={rc}\n\n{out or '(no output)'}"
            self.push_screen(CommandResultScreen(title=title, body=body))
            self.refresh_snapshot()

        def action_start_all(self) -> None:
            self._run_action('Start all services', 'start')

        def action_stop_all(self) -> None:
            self._run_action('Stop dashboard + minecraft', 'stop')

        def action_restart_all(self) -> None:
            self._run_action('Restart services', 'restart')

        def action_open_dashboard(self) -> None:
            self._run_action('Open dashboard', 'open')

        def action_doctor(self) -> None:
            self._run_action('ARX doctor', 'doctor')

        def action_cycle_theme(self) -> None:
            self.current_theme = next_tui_theme(self.current_theme)
            _save_ui_state({'theme': self.current_theme})
            self.push_screen(
                CommandResultScreen(
                    title='Theme switched',
                    body=f'Current theme: {self.current_theme}\nSaved to state/arx_ui.json',
                )
            )
            self._update_labels()

        def action_toggle_motion(self) -> None:
            self.reduced_motion = not self.reduced_motion
            _save_ui_state({'motion': not self.reduced_motion})
            mode = 'reduced' if self.reduced_motion else 'full'
            self.push_screen(
                CommandResultScreen(
                    title='Motion mode',
                    body=f'Now using {mode} motion\nSaved to state/arx_ui.json',
                )
            )
            self._update_labels()

        def action_log_dashboard(self) -> None:
            self.log_source = 'dashboard'
            self.refresh_snapshot()

        def action_log_server(self) -> None:
            self.log_source = 'server'
            self.refresh_snapshot()

        def action_log_ollama(self) -> None:
            self.log_source = 'ollama'
            self.refresh_snapshot()

        def action_log_playit(self) -> None:
            self.log_source = 'playit'
            self.refresh_snapshot()

    ArxTuiApp().run()
    return 0


def run_tui() -> int:
    try:
        importlib.import_module('textual.app')
    except ModuleNotFoundError:
        print('textual is not installed. Install with: ./.venv/bin/python -m pip install -r requirements.txt')
        return 1

    theme = resolve_tui_theme()
    reduced_motion = reduce_motion_enabled()
    return run_textual_app(theme=theme, reduced_motion=reduced_motion)


def main() -> int:
    parser = argparse.ArgumentParser(prog='arx_tui')
    parser.add_argument('--once', action='store_true', help='Print one snapshot and exit (debug)')
    args = parser.parse_args()

    if args.once:
        snap = _snapshot()
        print(_render_banner_text())
        print('')
        print(_render_services_text(snap))
        return 0

    return run_tui()


if __name__ == '__main__':
    raise SystemExit(main())
