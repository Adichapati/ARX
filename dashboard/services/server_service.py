import os
import platform
import re
import shlex
import subprocess
import time

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
    def _win_script_path() -> str:
        return str(MINECRAFT_DIR / 'start.bat')

    @staticmethod
    def _ensure_windows_start_script() -> None:
        p = MINECRAFT_DIR / 'start.bat'
        if p.exists():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            "cd /d %~dp0\r\n"
            "if not exist eula.txt echo eula=true>eula.txt\r\n"
            "where java >nul 2>nul\r\n"
            "if errorlevel 1 (\r\n"
            "  echo [ARX][ERROR] Java not found in PATH. Install Java 21+.\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
            "for /f \"tokens=3\" %%v in ('java -version 2^>^&1 ^| findstr /i \"version\"') do set JAVAVER=%%v\r\n"
            "set JAVAVER=%JAVAVER:\"=%\r\n"
            "for /f \"tokens=1 delims=.\" %%m in (\"%JAVAVER%\") do set MAJOR=%%m\r\n"
            "if \"%MAJOR%\"==\"1\" (\r\n"
            "  for /f \"tokens=2 delims=.\" %%m in (\"%JAVAVER%\") do set MAJOR=%%m\r\n"
            ")\r\n"
            "if %MAJOR% LSS 21 (\r\n"
            "  echo [ARX][ERROR] Java 21+ required. Detected Java %JAVAVER%.\r\n"
            "  echo Download: https://adoptium.net/temurin/releases/?version=21\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
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
            if os.name != 'nt':
                state['last_status_note'] = 'start failed (windows branch on non-windows host)'
                return 'failed: windows start is only available on Windows host'
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
            ServerService.send_console_command('stop', tier='admin', unsafe_ok=True)
            time.sleep(3)

        if ServerService.is_running():
            run("pkill -f 'server.jar' || true")
        if ServerService.tmux_session_exists():
            run(f"tmux kill-session -t {TMUX_SESSION} || true")

        state['last_action'] = 'stop'
        state['last_status_note'] = 'stop command sent'
        return 'stopped'

    @staticmethod
    def restart() -> str:
        ServerService.stop()
        time.sleep(1)
        msg = ServerService.start()
        state['last_action'] = 'restart'
        state['last_status_note'] = 'restart command sent'
        return 'restarted' if 'started' in msg or msg == 'already running' else msg

    @staticmethod
    def mc_query() -> dict:
        try:
            server = JavaServer(MC_HOST, MC_PORT, timeout=0.6)
            status = server.status()
            sample_names = []
            try:
                sample = getattr(status.players, 'sample', None) or []
                for p in sample:
                    n = getattr(p, 'name', None)
                    if n:
                        sample_names.append(str(n))
            except Exception:
                sample_names = []

            return {
                'online': True,
                'latency_ms': round(status.latency, 1),
                'version': getattr(status.version, 'name', 'unknown'),
                'players_online': int(getattr(status.players, 'online', 0)),
                'players_max': int(getattr(status.players, 'max', 20)),
                'player_names': sample_names,
            }
        except Exception:
            return {
                'online': False,
                'latency_ms': None,
                'version': 'unknown',
                'players_online': 0,
                'players_max': 20,
                'player_names': [],
            }

    @staticmethod
    def send_console_command(command: str, tier: str = 'safe', unsafe_ok: bool = False) -> dict:
        command = (command or '').strip()
        if not command:
            return {'ok': False, 'error': 'Empty command'}

        if ServerService._is_windows():
            return {'ok': False, 'error': 'console command passthrough is currently unavailable on native Windows runtime'}

        blocked_all = [r'^save-off\s*$']
        blocked_safe = [
            r'^stop\s*$', r'^restart\s*$', r'^op\s+@', r'^deop\s+@', r'^ban\s+@',
            r'^pardon\s+@', r'^whitelist\s+reload\s*$', r'^reload\s*$',
        ]
        blocked_moderate = [r'^stop\s*$', r'^restart\s*$']

        if not unsafe_ok:
            for pat in blocked_all:
                if re.match(pat, command, flags=re.IGNORECASE):
                    return {'ok': False, 'error': 'Blocked command by safety policy'}
            if tier == 'safe':
                for pat in blocked_safe:
                    if re.match(pat, command, flags=re.IGNORECASE):
                        return {'ok': False, 'error': 'Blocked in SAFE mode'}
            elif tier == 'moderate':
                for pat in blocked_moderate:
                    if re.match(pat, command, flags=re.IGNORECASE):
                        return {'ok': False, 'error': 'Blocked in MODERATE mode'}

        if not ServerService.tmux_session_exists() and not ServerService.is_running():
            return {'ok': False, 'error': 'Server is not running'}

        if not ServerService.tmux_session_exists():
            return {'ok': False, 'error': 'Console unavailable (server not in tmux). Restart once from dashboard.'}

        quoted = command.replace('"', '\\"')
        cp = run(f'tmux send-keys -t {TMUX_SESSION} "{quoted}" C-m')
        if cp.returncode != 0:
            return {'ok': False, 'error': (cp.stderr or 'Failed to send command').strip()}

        _console_history.append(command)
        state['last_action'] = f'cmd:{command.split()[0]}'
        state['last_status_note'] = f'command sent: {command}'
        return {'ok': True, 'message': 'Command sent'}
