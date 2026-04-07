import os
import platform
import re
import shlex
import shutil
import socket
import struct
import subprocess
import time

import psutil
from mcstatus import JavaServer

from ..config import (
    MC_HOST,
    MC_PORT,
    MINECRAFT_DIR,
    RCON_HOST,
    RCON_PASSWORD,
    RCON_PORT,
    TMUX_SESSION,
    _console_history,
    state,
)


def run(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)


class ServerService:
    @staticmethod
    def _is_windows() -> bool:
        return platform.system().lower().startswith('win')

    @staticmethod
    def _is_rcon_configured() -> bool:
        return bool((RCON_PASSWORD or '').strip())

    @staticmethod
    def _send_rcon_command(command: str) -> dict:
        """Send command over Minecraft RCON (protocol-level; no third-party dependency)."""
        host = (RCON_HOST or '127.0.0.1').strip() or '127.0.0.1'
        port = int(RCON_PORT)
        password = (RCON_PASSWORD or '').strip()
        if not password:
            return {'ok': False, 'error': 'RCON password missing (RCON_PASSWORD)'}

        req_id = int(time.time() * 1000) & 0x7FFFFFFF

        def _pkt(pid: int, ptype: int, body: str) -> bytes:
            payload = body.encode('utf-8') + b'\x00\x00'
            size = 4 + 4 + len(payload)
            return struct.pack('<iii', size, pid, ptype) + payload

        def _recv(sock: socket.socket) -> tuple[int, int, str]:
            hdr = sock.recv(4)
            if len(hdr) < 4:
                raise RuntimeError('RCON read failed (size header)')
            size = struct.unpack('<i', hdr)[0]
            data = b''
            while len(data) < size:
                chunk = sock.recv(size - len(data))
                if not chunk:
                    break
                data += chunk
            if len(data) < 8:
                raise RuntimeError('RCON read failed (payload)')
            pid, ptype = struct.unpack('<ii', data[:8])
            body = data[8:-2].decode('utf-8', errors='replace') if len(data) >= 10 else ''
            return pid, ptype, body

        try:
            with socket.create_connection((host, port), timeout=2.0) as sock:
                sock.settimeout(2.0)
                sock.sendall(_pkt(req_id, 3, password))  # auth
                auth_id, _auth_type, _auth_body = _recv(sock)
                if auth_id == -1:
                    return {'ok': False, 'error': 'RCON auth failed (check RCON_PASSWORD)'}

                sock.sendall(_pkt(req_id + 1, 2, command))  # command
                _cmd_id, _cmd_type, _cmd_body = _recv(sock)

            out = (_cmd_body or '').strip()
            low = out.lower()
            fail_markers = (
                'unknown or incomplete command',
                'incorrect argument for command',
                'expected ',
                'no player was found',
                'no entity was found',
                'cannot find',
                'failed to execute',
                'usage:',
            )
            if out and any(m in low for m in fail_markers):
                return {'ok': False, 'error': f'Minecraft rejected command: {out[:240]}'}

            state['rcon_last_ok_at'] = time.time()
            _console_history.append(command)
            state['last_action'] = f'cmd:{command.split()[0]}'
            state['last_status_note'] = f'command sent (rcon): {command}'
            return {'ok': True, 'message': 'Command sent', 'output': out}
        except Exception as e:
            return {'ok': False, 'error': f'RCON command failed: {e}'}

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
            if os.name != 'nt':
                state['last_status_note'] = 'start failed (windows branch on non-windows host)'
                return 'failed: windows start is only available on Windows host'

            flags = 0
            flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)

            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= getattr(subprocess, 'STARTF_USESHOWWINDOW', 0)
                startupinfo.wShowWindow = getattr(subprocess, 'SW_HIDE', 0)

            java_cmd = shutil.which('javaw') or shutil.which('java')
            if not java_cmd:
                state['last_status_note'] = 'start failed (windows): java not found'
                return 'failed: java/javaw not found in PATH'

            jar = str(MINECRAFT_DIR / 'server.jar')
            if not os.path.exists(jar):
                state['last_status_note'] = 'start failed (windows): server.jar missing'
                return f'failed: missing {jar}'

            eula = MINECRAFT_DIR / 'eula.txt'
            if not eula.exists():
                eula.write_text('eula=true\n', encoding='utf-8')

            try:
                os.makedirs(str(MINECRAFT_DIR / 'logs'), exist_ok=True)
                out = open(MINECRAFT_DIR / 'logs' / 'arx-server.log', 'ab')

                props_path = MINECRAFT_DIR / 'server.properties'
                props = {}
                if props_path.exists():
                    for line in props_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        k, v = line.split('=', 1)
                        props[k.strip()] = v.strip()
                props['enable-rcon'] = 'true'
                props['rcon.port'] = str(RCON_PORT)
                props['rcon.password'] = (RCON_PASSWORD or '').strip() or 'arx-local-rcon'
                props['broadcast-rcon-to-ops'] = 'false'
                lines = ['#Minecraft server properties', '#Updated by ARX dashboard']
                for k in sorted(props.keys()):
                    lines.append(f'{k}={props[k]}')
                props_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

                subprocess.Popen(
                    [java_cmd, '-Xms1G', '-Xmx2G', '-jar', jar, 'nogui'],
                    cwd=str(MINECRAFT_DIR),
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=out,
                    creationflags=flags,
                    startupinfo=startupinfo,
                    close_fds=True,
                )
                state['last_status_note'] = 'start command sent (windows hidden process + rcon enabled)'
                return 'started'
            except Exception as e:
                state['last_status_note'] = 'start failed (windows)'
                return f'failed: {e}'

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

        if not ServerService.is_running():
            return {'ok': False, 'error': 'Server is not running'}

        if ServerService._is_windows():
            if not ServerService._is_rcon_configured():
                return {'ok': False, 'error': 'Console unavailable: RCON not configured'}

            # RCON can take a few seconds after process startup; retry briefly.
            last_err = None
            for _ in range(8):
                res = ServerService._send_rcon_command(command)
                if res.get('ok'):
                    return res
                last_err = res.get('error', 'RCON command failed')
                if 'auth failed' in str(last_err).lower():
                    break
                time.sleep(0.35)
            return {'ok': False, 'error': last_err or 'RCON command failed'}

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
