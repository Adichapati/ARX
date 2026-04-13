#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import argparse
import importlib
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil

try:
    from scripts.ui.style_engine import resolve_style, style_pack
except Exception:  # pragma: no cover
    from ui.style_engine import resolve_style, style_pack


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'


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


def run_textual_app() -> int:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Header, Static, TextLog

    class CommandResultScreen(ModalScreen[None]):
        BINDINGS = [Binding('escape', 'dismiss', 'Close')]

        def __init__(self, title: str, body: str) -> None:
            super().__init__()
            self._title = title
            self._body = body

        def compose(self) -> ComposeResult:
            yield Container(
                Static(self._title, id='cmd-title'),
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
        CSS = """
        Screen { background: #0b0f14; }
        #layout { height: 1fr; }
        #left { width: 2fr; padding: 1 2; }
        #right { width: 1fr; padding: 1 1; border-left: solid #2f3b4a; }
        #banner { color: #6ee7ff; }
        #services { margin-top: 1; color: #d1f7ff; }
        #hotkeys { margin-top: 1; color: #9ca3af; }
        #logs-title { color: #f9d65c; }
        #logs-box { height: 1fr; }
        #cmd-modal {
            width: 80%;
            height: 70%;
            margin: 2 4;
            border: round #4c7aaf;
            padding: 1;
            background: #111827;
        }
        #cmd-title { color: #93c5fd; }
        #cmd-log { height: 1fr; margin-top: 1; }
        """

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
        ]

        log_source = reactive('dashboard')

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id='layout'):
                with Container(id='left'):
                    yield Static(_render_banner_text(), id='banner')
                    yield Static('', id='services')
                    yield Static('Hotkeys: [s]start [x]stop [r]restart [o]open [d]doctor [1-4]logs [q]quit', id='hotkeys')
                with Container(id='right'):
                    yield Static('Logs (1 dashboard, 2 server, 3 ollama, 4 playit)', id='logs-title')
                    yield TextLog(id='logs-box', wrap=True, highlight=False)
            yield Footer()

        def on_mount(self) -> None:
            self.title = 'ARX TUI'
            self.sub_title = 'Agentic Runtime for eXecution'
            self.set_interval(1.0, self.refresh_snapshot)
            self.refresh_snapshot()

        def refresh_snapshot(self) -> None:
            snap = _snapshot()
            self.query_one('#services', Static).update(_render_services_text(snap))

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

    return run_textual_app()


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
