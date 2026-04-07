import os
import platform
import shlex
import subprocess
import time
import urllib.request
from pathlib import Path

import psutil
from mcstatus import JavaServer

from ..config import MC_HOST, MC_PORT, MINECRAFT_DIR, TMUX_SESSION, _console_history, state


def run(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)


class ServerService:
    @staticmethod
    def _is_windows() -> bool:
        return platform.system().lower().startswith('win')

    @staticmethod
    def _win_script_path() -> Path:
        return MINECRAFT_DIR / 'start.bat'

    @staticmethod
    def _ensure_windows_start_script() -> None:
        p = ServerService._win_script_path()
        if p.exists():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "@echo off\r\n"
            "cd /d %~dp0\r\n"
            "if not exist eula.txt echo eula=true>eula.txt\r\n"
            "java -Xms1G -Xmx2G -jar server.jar nogui\r\n",
            encoding='utf-8',
        )

    @staticmethod
    def is_running() -> bool:
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                name = (proc.info.get('name') or '').lower()
                cmd = ' '.join(proc.info.get('cmdline') or [])
                if 'java' in name and 'server.jar' in cmd:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    @staticmethod
    def tmux_session_exists() -> bool:
        if ServerService._is_windows():
            return False
        cp = run(f"tmux has-session -t {TMUX_SESSION} 2>/dev/null")
        return cp.returncode == 0

    @staticmethod
    def start() -> str:
        if ServerService.is_running():
            return 'already running'

        state['last_action'] = 'start'

        if ServerService._is_windows():
            ServerService._ensure_windows_start_script()
            script = ServerService._win_script_path()
            cmd = f'cmd /c start "ARX-Minecraft" /D "{MINECRAFT_DIR}" "{script}"'
            cp = run(cmd)
            if cp.returncode == 0:
                state['last_status_note'] = 'start command sent (windows detached process)'
                return 'started'
            state['last_status_note'] = 'start failed (windows)'
            return f'failed: {(cp.stderr or cp.stdout or "start failed").strip()}'

        cmd = f"tmux new-session -d -s {TMUX_SESSION} 'cd {shlex.quote(str(MINECRAFT_DIR))} && ./start.sh'"
        cp = run(cmd)
        if cp.returncode == 0:
            state['last_status_note'] = 'start command sent (tmux)'
            return 'started'

        cp2 = run(f'cd {shlex.quote(str(MINECRAFT_DIR))} && nohup ./start.sh > /tmp/minecraft-server.out 2>&1 &')
        state['last_status_note'] = 'start command sent (nohup fallback)'
        return 'started' if cp2.returncode == 0 else f'failed: {(cp.stderr or cp2.stderr).strip()}'

    @staticmethod
    def stop() -> str:
        if ServerService._is_windows():
            # Graceful stop via stdin console is not available on detached cmd process.
            # Fallback: kill java server process by matching server.jar.
            stopped_any = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    cmd = ' '.join(proc.info.get('cmdline') or [])
                    if 'java' in name and 'server.jar' in cmd:
                        proc.terminate()
                        stopped_any = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            time.sleep(1.5)
            state['last_action'] = 'stop'
            state['last_status_note'] = 'stop command issued (windows terminate java)'
            return 'stopped' if stopped_any else 'not running'

        if ServerService.tmux_session_exists():
            ServerService.send_console_command('stop', unsafe_ok=True)
            time.sleep(2)
        if ServerService.tmux_session_exists():
            run(f"tmux kill-session -t {TMUX_SESSION} || true")
        state['last_action'] = 'stop'
        state['last_status_note'] = 'stop command sent'
        return 'stopped'

    @staticmethod
    def restart() -> str:
        ServerService.stop()
        time.sleep(1)
        r = ServerService.start()
        state['last_action'] = 'restart'
        state['last_status_note'] = 'restart command sent'
        return 'restarted' if 'started' in r or r == 'already running' else r

    @staticmethod
    def send_console_command(command: str, unsafe_ok: bool = False) -> dict:
        command = (command or '').strip()
        if not command:
            return {'ok': False, 'error': 'empty command'}

        if ServerService._is_windows():
            return {'ok': False, 'error': 'console command passthrough is currently unavailable on native Windows runtime'}

        if not ServerService.tmux_session_exists() and not ServerService.is_running():
            return {'ok': False, 'error': 'server is not running'}
        if not ServerService.tmux_session_exists():
            return {'ok': False, 'error': 'console unavailable (not running in tmux)'}

        quoted = command.replace('"', '\\"')
        cp = run(f'tmux send-keys -t {TMUX_SESSION} "{quoted}" C-m')
        if cp.returncode != 0:
            return {'ok': False, 'error': (cp.stderr or 'failed to send').strip()}
        _console_history.append(command)
        state['last_action'] = f'cmd:{command.split()[0]}'
        state['last_status_note'] = f'command sent: {command}'
        return {'ok': True, 'message': 'command sent'}

    @staticmethod
    def mc_query() -> dict:
        try:
            s = JavaServer(MC_HOST, MC_PORT, timeout=0.6).status()
            names = []
            sample = getattr(s.players, 'sample', None) or []
            for p in sample:
                n = getattr(p, 'name', None)
                if n:
                    names.append(str(n))
            return {
                'online': True,
                'version': getattr(s.version, 'name', 'unknown'),
                'players_online': int(getattr(s.players, 'online', 0)),
                'players_max': int(getattr(s.players, 'max', 20)),
                'player_names': names,
            }
        except Exception:
            return {'online': False, 'version': 'unknown', 'players_online': 0, 'players_max': 20, 'player_names': []}

    @staticmethod
    def runtime_health() -> dict:
        ollama_ok = False
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=1.2) as r:
                ollama_ok = r.status == 200
        except Exception:
            ollama_ok = False

        try:
            java_running = ServerService.is_running()
        except Exception:
            java_running = False

        if ServerService._is_windows():
            tmux_ok = None
        else:
            try:
                tmux_ok = ServerService.tmux_session_exists()
            except Exception:
                tmux_ok = False

        q = ServerService.mc_query()
        return {
            'ollama': 'ok' if ollama_ok else 'down',
            'tmux': 'n/a' if tmux_ok is None else ('ok' if tmux_ok else 'down'),
            'java': 'ok' if java_running else 'down',
            'server_ping': 'ok' if q.get('online') else 'down',
            'server_version': q.get('version', 'unknown'),
        }
