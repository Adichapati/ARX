#!/usr/bin/env python3
"""ARX TUI — polished Textual-based terminal interface with animated ASCII branding."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import importlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil

try:
    from scripts.ui.style_engine import (
        resolve_style,
        style_pack,
        resolve_theme,
        next_theme,
        get_palette,
        AVAILABLE_THEMES,
        load_ui_state,
        save_ui_state,
    )
    from scripts.ui.ascii_assets import (
        build_reveal_frames,
        build_fade_frames,
        TAGLINE_STYLED,
        spinner_cycle,
        STATUS_UP,
        STATUS_DOWN,
    )
    from scripts.ui.terminal_caps import supports_unicode, can_animate, terminal_width
except Exception:  # pragma: no cover
    from ui.style_engine import (
        resolve_style,
        style_pack,
        resolve_theme,
        next_theme,
        get_palette,
        AVAILABLE_THEMES,
        load_ui_state,
        save_ui_state,
    )
    from ui.ascii_assets import (
        build_reveal_frames,
        build_fade_frames,
        TAGLINE_STYLED,
        spinner_cycle,
        STATUS_UP,
        STATUS_DOWN,
    )
    from ui.terminal_caps import supports_unicode, can_animate, terminal_width


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'


# ---------------------------------------------------------------------------
#  Config helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
#  Process / port detection
# ---------------------------------------------------------------------------

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


def _tail(path: Path, lines: int = 12) -> str:
    if not path.exists():
        return '(log not found)'
    try:
        data = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception:
        return '(unable to read log)'
    if not data:
        return '(empty log)'
    return '\n'.join(data[-lines:])


# ---------------------------------------------------------------------------
#  UI state persistence
# ---------------------------------------------------------------------------

def _ui_state() -> dict:
    return load_ui_state(ROOT)


def _save_ui_state(patch_obj: dict) -> None:
    data = _ui_state()
    data.update(patch_obj)
    save_ui_state(ROOT, data)


def resolve_tui_theme() -> str:
    return resolve_theme(ROOT)


def reduce_motion_enabled() -> bool:
    env = os.environ.get('ARX_REDUCE_MOTION', '').strip().lower()
    if env in {'1', 'true', 'yes', 'on'}:
        return True
    state_motion = _ui_state().get('motion', True)
    if isinstance(state_motion, bool):
        return not state_motion
    return False


def next_tui_theme(current: str) -> str:
    return next_theme(current)


# ---------------------------------------------------------------------------
#  Service snapshot
# ---------------------------------------------------------------------------

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
    return _tail(path, lines=12)


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
        dashboard_addr=f'http://localhost:{bind_port()}/',
        minecraft_path=str(minecraft_dir()),
    )


def _run_arx_cli_command(*args: str) -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / 'scripts' / 'arx_cli.py'), *args]
    cp = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True,
        encoding='utf-8', errors='replace',
    )
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


# ---------------------------------------------------------------------------
#  CSS builder
# ---------------------------------------------------------------------------

def build_tui_css(theme: str, reduced_motion: bool) -> str:
    p = get_palette(theme)
    transition = '' if reduced_motion else '        transition: color 180ms ease-in-out, background 180ms ease-in-out, border 180ms ease-in-out;\n'
    return (
        "        Screen {\n"
        f"            background: {p['bg']};\n"
        "        }\n\n"
        "        #layout {\n"
        "            height: 1fr;\n"
        "        }\n"
        "        #left {\n"
        "            width: 2fr;\n"
        "            padding: 1 2;\n"
        "        }\n"
        "        #right {\n"
        "            width: 1fr;\n"
        "            padding: 1 1;\n"
        f"            border-left: tall {p['border']};\n"
        "        }\n\n"
        "        #banner {\n"
        f"            color: {p['banner']};\n"
        "        }\n"
        "        #tagline {\n"
        f"            color: {p['tagline']};\n"
        "            margin-top: 0;\n"
        "            text-style: italic;\n"
        "        }\n\n"
        "        #services {\n"
        "            margin-top: 1;\n"
        f"{transition}"
        "        }\n"
        "        .service-card {\n"
        "            padding: 0 1;\n"
        "            margin-bottom: 0;\n"
        f"{transition}"
        "        }\n"
        "        .service-up {\n"
        f"            color: {p['success']};\n"
        "        }\n"
        "        .service-down {\n"
        f"            color: {p['text_muted']};\n"
        "        }\n"
        "        .service-label {\n"
        f"            color: {p['text']};\n"
        "        }\n"
        "        .service-detail {\n"
        f"            color: {p['text_muted']};\n"
        "        }\n\n"
        "        #status-bar {\n"
        "            dock: bottom;\n"
        "            height: 1;\n"
        f"            background: {p['surface']};\n"
        f"            color: {p['text_muted']};\n"
        "            padding: 0 1;\n"
        "        }\n"
        "        #hotkeys {\n"
        "            margin-top: 1;\n"
        f"            color: {p['text_muted']};\n"
        "        }\n"
        "        .hotkey-key {\n"
        f"            color: {p['primary']};\n"
        "            text-style: bold;\n"
        "        }\n\n"
        "        #theme-chip {\n"
        f"            color: {p['accent']};\n"
        "            margin-top: 1;\n"
        "        }\n\n"
        "        #logs-title {\n"
        f"            color: {p['accent']};\n"
        "            text-style: bold;\n"
        "        }\n"
        "        #logs-box {\n"
        "            height: 1fr;\n"
        f"            scrollbar-color: {p['scrollbar']};\n"
        f"            scrollbar-color-hover: {p['scrollbar_hover']};\n"
        f"            scrollbar-color-active: {p['primary']};\n"
        f"            border: round {p['border']};\n"
        "            padding: 0 1;\n"
        f"            background: {p['surface']};\n"
        "        }\n\n"
        "        #cmd-modal {\n"
        "            width: 80%;\n"
        "            height: 70%;\n"
        "            margin: 2 4;\n"
        f"            border: round {p['border_focus']};\n"
        "            padding: 1 2;\n"
        f"            background: {p['card_bg']};\n"
        "        }\n"
        "        #cmd-title {\n"
        f"            color: {p['primary']};\n"
        "            text-style: bold;\n"
        "        }\n"
        "        #cmd-log {\n"
        "            height: 1fr;\n"
        "            margin-top: 1;\n"
        f"            border: round {p['border']};\n"
        f"            background: {p['surface']};\n"
        f"            scrollbar-color: {p['scrollbar']};\n"
        f"            scrollbar-color-hover: {p['scrollbar_hover']};\n"
        "        }\n\n"
        "        #env-badge {\n"
        f"            color: {p['text_muted']};\n"
        "            text-style: dim;\n"
        "        }\n"
    )


# ---------------------------------------------------------------------------
#  Textual TUI App
# ---------------------------------------------------------------------------

def run_textual_app(theme: str, reduced_motion: bool) -> int:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Header, Static, RichLog

    initial_theme = theme if theme in AVAILABLE_THEMES else 'neon_underground'
    initial_reduced = bool(reduced_motion)

    # -- Command result modal --

    class CommandResultScreen(ModalScreen[None]):
        BINDINGS = [Binding('escape', 'dismiss', 'Close')]

        def __init__(self, title: str, body: str) -> None:
            super().__init__()
            self._title = title
            self._body = body

        def compose(self) -> ComposeResult:
            yield Container(
                Static(self._title, id='cmd-title'),
                RichLog(id='cmd-log', wrap=True, highlight=True, markup=True),
                id='cmd-modal',
            )

        def on_mount(self) -> None:
            log = self.query_one('#cmd-log', RichLog)
            for line in (self._body or '(no output)').splitlines() or ['(no output)']:
                log.write(line)

        def action_dismiss(self) -> None:
            self.dismiss(None)

    # -- Service card rendering --

    def _render_service_card(name: str, up: bool, detail: str) -> str:
        icon = '\u25cf ' if up else '\u25cb '
        status = 'UP' if up else 'DOWN'
        status_class = 'service-up' if up else 'service-down'
        return f"[{status_class}]{icon}{status}[/]  [bold]{name}[/bold]  [dim]{detail}[/dim]"

    def _render_services_rich(s: ServiceSnapshot) -> str:
        lines = [
            _render_service_card('Dashboard', s.dashboard_up, s.dashboard_addr),
            _render_service_card('Minecraft', s.minecraft_up, s.minecraft_path),
            _render_service_card('Ollama', s.ollama_up, 'http://127.0.0.1:11434'),
        ]
        if s.playit_enabled:
            lines.append(_render_service_card('Playit', s.playit_up, f'url={s.playit_url}'))
        else:
            lines.append('[dim]\u25cb Playit  (disabled)[/dim]')
        return '\n'.join(lines)

    def _render_hotkeys() -> str:
        keys = [
            ('[bold cyan]s[/]', 'start'),
            ('[bold cyan]x[/]', 'stop'),
            ('[bold cyan]r[/]', 'restart'),
            ('[bold cyan]o[/]', 'open'),
            ('[bold cyan]d[/]', 'doctor'),
            ('[bold cyan]1-4[/]', 'logs'),
            ('[bold cyan]t[/]', 'theme'),
            ('[bold cyan]m[/]', 'motion'),
            ('[bold cyan]q[/]', 'quit'),
        ]
        return '  '.join(f'{k} {v}' for k, v in keys)

    # -- Main TUI app --

    class ArxTuiApp(App):
        CSS = build_tui_css(initial_theme, initial_reduced)

        BINDINGS = [
            Binding('q', 'quit', 'Quit', priority=True),
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
        _reveal_step = reactive(0)
        _startup_done = reactive(False)

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id='layout'):
                with Container(id='left'):
                    yield Static('', id='banner')
                    yield Static(TAGLINE_STYLED, id='tagline')
                    yield Static('', id='services')
                    yield Static('', id='theme-chip')
                    yield Static('', id='hotkeys')
                    yield Static('', id='env-badge')
                with Container(id='right'):
                    yield Static('', id='logs-title')
                    yield RichLog(id='logs-box', wrap=True, highlight=True, markup=True)
            yield Footer()

        def on_mount(self) -> None:
            self.title = 'ARX'
            self.sub_title = 'Agentic Runtime for eXecution'

            os_name = platform.system()
            py_ver = f'{sys.version_info.major}.{sys.version_info.minor}'
            self.query_one('#env-badge', Static).update(
                f'[dim]{os_name} \u00b7 Python {py_ver} \u00b7 {bind_host()}:{bind_port()}[/dim]'
            )

            self.query_one('#hotkeys', Static).update(_render_hotkeys())

            banner_text = _render_banner_text()
            if not self.reduced_motion and can_animate():
                self._reveal_frames = build_reveal_frames(banner_text)
                self._reveal_step = 0
                self._startup_done = False
                self._reveal_timer = self.set_interval(0.06, self._animate_reveal)
            else:
                self.query_one('#banner', Static).update(banner_text)
                self._startup_done = True

            interval = 2.0 if self.reduced_motion else 1.2
            self.set_interval(interval, self.refresh_snapshot)
            self.refresh_snapshot()

        def _animate_reveal(self) -> None:
            if self._reveal_step >= len(self._reveal_frames):
                self._reveal_timer.stop()
                self._startup_done = True
                return
            self.query_one('#banner', Static).update(
                self._reveal_frames[self._reveal_step]
            )
            self._reveal_step += 1

        def _update_labels(self) -> None:
            self.query_one('#logs-title', Static).update(
                f'\u256d\u2500 Logs \u00b7 [bold]{self.log_source.upper()}[/bold] \u00b7 switch with [bold cyan]1/2/3/4[/bold cyan]'
            )
            motion_label = 'reduced' if self.reduced_motion else 'full'
            self.query_one('#theme-chip', Static).update(
                f'[dim]theme:[/dim] [bold]{self.current_theme}[/bold]  '
                f'[dim]motion:[/dim] [bold]{motion_label}[/bold]'
            )

        def refresh_snapshot(self) -> None:
            snap = _snapshot()
            self.query_one('#services', Static).update(_render_services_rich(snap))
            self._update_labels()

            log_widget = self.query_one('#logs-box', RichLog)
            log_widget.clear()
            for line in _log_snippet(self.log_source).splitlines():
                log_widget.write(line)

        def _show_result(self, title: str, body: str) -> None:
            self.push_screen(CommandResultScreen(title=title, body=body))
            self.set_timer(0.3, self.refresh_snapshot)

        def _run_action(self, title: str, *argv: str) -> None:
            rc, out = _run_arx_cli_command(*argv)
            cmd_str = ' '.join(argv)
            body = f"[dim]$ arx {cmd_str}[/dim]\n[dim]exit={rc}[/dim]\n\n{out or '(no output)'}"
            self._show_result(title, body)

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
            new_theme = next_tui_theme(self.current_theme)
            self.current_theme = new_theme
            _save_ui_state({'theme': new_theme})
            self._show_result(
                'Theme switched',
                f'[bold]Theme:[/bold] {new_theme}\n\n'
                f'[dim]Restart TUI for full theme refresh.[/dim]\n'
                f'Saved to state/arx_ui.json',
            )
            self._update_labels()

        def action_toggle_motion(self) -> None:
            self.reduced_motion = not self.reduced_motion
            _save_ui_state({'motion': not self.reduced_motion})
            mode = 'reduced' if self.reduced_motion else 'full'
            self._show_result(
                'Motion mode',
                f'[bold]Motion:[/bold] {mode}\n\nSaved to state/arx_ui.json',
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


# ---------------------------------------------------------------------------
#  Entry points
# ---------------------------------------------------------------------------

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
        print(TAGLINE_STYLED)
        print('')
        snap_data = _snapshot()
        lines = [
            f'Dashboard : {"UP" if snap_data.dashboard_up else "DOWN"}  ({snap_data.dashboard_addr})',
            f'Minecraft : {"UP" if snap_data.minecraft_up else "DOWN"}  ({snap_data.minecraft_path})',
            f'Ollama    : {"UP" if snap_data.ollama_up else "DOWN"}  (http://127.0.0.1:11434)',
            f'Playit    : {"UP" if snap_data.playit_up else "DOWN"}  (enabled={str(snap_data.playit_enabled).lower()}, url={snap_data.playit_url})',
        ]
        print('\n'.join(lines))
        return 0

    return run_tui()


if __name__ == '__main__':
    raise SystemExit(main())
