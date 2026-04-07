#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import psutil
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / 'state'
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


def _set_env_key(key: str, value: str) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding='utf-8', errors='ignore').splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        raw = line.strip()
        if raw.startswith('#') or '=' not in line:
            out.append(line)
            continue
        k, _v = line.split('=', 1)
        if k.strip() == key:
            out.append(f'{key}={value}')
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f'{key}={value}')
    ENV_PATH.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')


def _set_runtime_context_in_state(tokens: int) -> None:
    cfg_path = STATE_DIR / 'arx_config.json'
    data: dict = {}
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding='utf-8', errors='ignore'))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
    data['gemma_context_size'] = int(tokens)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def bind_host() -> str:
    return cfg('BIND_HOST', '0.0.0.0')


def bind_port() -> int:
    try:
        return int(cfg('BIND_PORT', '18890'))
    except Exception:
        return 18890


def tmux_session() -> str:
    return cfg('MC_TMUX_SESSION', 'mc_server_arx')


def minecraft_dir() -> Path:
    return Path(cfg('MINECRAFT_DIR', str((ROOT / 'app' / 'minecraft_server').resolve()))).resolve()


def dashboard_url() -> str:
    return f"http://localhost:{bind_port()}/"


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


def _ollama_ok() -> bool:
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=0.8) as r:
            return r.status == 200
    except Exception:
        return False


def _win_creationflags() -> int:
    flags = 0
    flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    return flags


def _win_startupinfo_hidden():
    if os.name != 'nt' or not hasattr(subprocess, 'STARTUPINFO'):
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= getattr(subprocess, 'STARTF_USESHOWWINDOW', 0)
    si.wShowWindow = getattr(subprocess, 'SW_HIDE', 0)
    return si


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


def _tmux_has_session(name: str) -> bool:
    if os.name == 'nt' or not shutil.which('tmux'):
        return False
    cp = subprocess.run(['tmux', 'has-session', '-t', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cp.returncode == 0


def _terminate_processes(procs: list[psutil.Process], timeout: float = 4.0) -> int:
    """Best-effort terminate that never raises on AccessDenied/NoSuchProcess."""
    if not procs:
        return 0

    seen: set[int] = set()
    touched = 0

    for p in procs:
        try:
            pid = int(p.pid)
        except Exception:
            continue
        if pid in seen:
            continue
        seen.add(pid)

        # Try graceful terminate first.
        try:
            p.terminate()
            touched += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:
            pass

        # Wait a bit, but never fail if wait is not permitted.
        try:
            p.wait(timeout=timeout)
            continue
        except (psutil.TimeoutExpired, psutil.AccessDenied):
            pass
        except (psutil.NoSuchProcess, ProcessLookupError):
            continue
        except Exception:
            pass

        # Escalate to kill if still alive and accessible.
        try:
            p.kill()
            touched += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass

    return touched


def _start_ollama() -> tuple[bool, str]:
    if _ollama_ok():
        return True, 'already running'
    if not shutil.which('ollama'):
        return False, 'ollama command not found'

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = STATE_DIR / 'ollama.log'

    try:
        with log_path.open('ab') as out:
            if os.name == 'nt':
                subprocess.Popen(
                    ['ollama', 'serve'],
                    stdout=out,
                    stderr=out,
                    stdin=subprocess.DEVNULL,
                    creationflags=_win_creationflags(),
                    startupinfo=_win_startupinfo_hidden(),
                )
            else:
                subprocess.Popen(['ollama', 'serve'], stdout=out, stderr=out, stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        return False, f'failed to start ollama: {e}'

    for _ in range(20):
        if _ollama_ok():
            return True, 'started'
        time.sleep(0.5)
    return False, 'ollama did not become ready in time'


def _stop_ollama() -> tuple[bool, str]:
    procs = _find_ollama_procs()
    if not procs:
        return True, 'not running'
    n = _terminate_processes(procs)
    return True, f'stopped {n} process(es)'


def _start_server() -> tuple[bool, str]:
    if _find_server_procs():
        return True, 'already running'

    mc = minecraft_dir()
    if os.name == 'nt':
        # Start directly with java/javaw to avoid visible cmd windows.
        java_cmd = shutil.which('javaw') or shutil.which('java')
        if not java_cmd:
            return False, 'java/javaw not found in PATH'

        jar = mc / 'server.jar'
        if not jar.exists():
            return False, f'missing {jar}'

        eula = mc / 'eula.txt'
        if not eula.exists():
            eula.write_text('eula=true\n', encoding='utf-8')

        # Ensure Windows runtime has RCON enabled so dashboard console/buttons work.
        props_path = mc / 'server.properties'
        props: dict[str, str] = {}
        if props_path.exists():
            for line in props_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                props[k.strip()] = v.strip()
        props['enable-rcon'] = 'true'
        props['rcon.port'] = cfg('RCON_PORT', '25575')
        props['rcon.password'] = cfg('RCON_PASSWORD', 'arx-local-rcon')
        props['broadcast-rcon-to-ops'] = 'false'
        lines = ['#Minecraft server properties', '#Updated by ARX CLI']
        for k in sorted(props.keys()):
            lines.append(f'{k}={props[k]}')
        props_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

        try:
            with (STATE_DIR / 'server.log').open('ab') as out:
                subprocess.Popen(
                    [java_cmd, '-Xms1G', '-Xmx2G', '-jar', str(jar), 'nogui'],
                    cwd=str(mc),
                    stdout=out,
                    stderr=out,
                    stdin=subprocess.DEVNULL,
                    creationflags=_win_creationflags(),
                    startupinfo=_win_startupinfo_hidden(),
                )
            return True, 'start requested'
        except Exception as e:
            return False, f'failed: {e}'

    start_sh = mc / 'start.sh'
    if not start_sh.exists():
        return False, f'missing {start_sh}'

    sess = tmux_session()
    if shutil.which('tmux'):
        cp = subprocess.run(['tmux', 'new-session', '-d', '-s', sess, f'cd {mc} && ./start.sh'], capture_output=True, text=True)
        if cp.returncode == 0:
            return True, f'started in tmux session {sess}'

    try:
        with (STATE_DIR / 'server.out.log').open('ab') as out:
            subprocess.Popen(['bash', '-lc', f'cd {mc} && ./start.sh'], stdout=out, stderr=out, stdin=subprocess.DEVNULL, start_new_session=True)
        return True, 'started via nohup fallback'
    except Exception as e:
        return False, f'failed: {e}'


def _stop_server() -> tuple[bool, str]:
    if os.name != 'nt':
        sess = tmux_session()
        if _tmux_has_session(sess):
            try:
                subprocess.run(['tmux', 'send-keys', '-t', sess, 'stop', 'C-m'], check=False)
                time.sleep(2.5)
                subprocess.run(['tmux', 'kill-session', '-t', sess], check=False)
            except Exception:
                pass

    procs = _find_server_procs()
    n = _terminate_processes(procs)

    # On Windows, Java may be owned by a different privilege context.
    # Treat "still running but inaccessible" as actionable guidance, not a crash.
    still_running = bool(_find_server_procs())
    if still_running and os.name == 'nt':
        return False, 'server process still running (likely permission denied). Re-run terminal as Administrator or stop javaw.exe from Task Manager.'

    if n == 0 and not still_running:
        return True, 'not running'
    return True, f'stopped {n} process(es)'


def _start_dashboard() -> tuple[bool, str]:
    if _find_dashboard_procs() or _port_open('127.0.0.1', bind_port()):
        return True, 'already running'

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = STATE_DIR / 'dashboard.log'

    py = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not py.exists():
        return False, f'missing venv python: {py}'

    cmd = [str(py), '-m', 'uvicorn', 'main:app', '--host', bind_host(), '--port', str(bind_port())]

    try:
        with log_path.open('ab') as out:
            if os.name == 'nt':
                subprocess.Popen(
                    cmd,
                    cwd=str(ROOT),
                    stdout=out,
                    stderr=out,
                    stdin=subprocess.DEVNULL,
                    creationflags=_win_creationflags(),
                    startupinfo=_win_startupinfo_hidden(),
                )
            else:
                subprocess.Popen(cmd, cwd=str(ROOT), stdout=out, stderr=out, stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        return False, f'failed: {e}'

    for _ in range(20):
        if _port_open('127.0.0.1', bind_port()):
            return True, 'started'
        time.sleep(0.3)
    return False, 'did not become reachable in time'


def _stop_dashboard() -> tuple[bool, str]:
    procs = _find_dashboard_procs()
    n = _terminate_processes(procs)
    if n == 0:
        return True, 'not running'
    return True, f'stopped {n} process(es)'


def _tail(path: Path, lines: int) -> str:
    if not path.exists():
        return f'log file not found: {path}'
    data = path.read_text(encoding='utf-8', errors='replace').splitlines()
    return '\n'.join(data[-lines:])


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


def _start_playit() -> tuple[bool, str]:
    if _playit_running():
        return True, 'already running'

    exe = shutil.which('playit')
    if not exe:
        if os.name == 'nt':
            exe = str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'playit_gg' / 'bin' / 'playit.exe')
            if not Path(exe).exists():
                return False, 'playit not found; install from https://playit.gg/download'
        else:
            return False, 'playit not found; install from https://playit.gg/download'

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = STATE_DIR / 'playit.log'
    try:
        with log_path.open('ab') as out:
            if os.name == 'nt':
                subprocess.Popen(
                    [exe],
                    cwd=str(ROOT),
                    stdout=out,
                    stderr=out,
                    stdin=subprocess.DEVNULL,
                    creationflags=_win_creationflags(),
                    startupinfo=_win_startupinfo_hidden(),
                )
            else:
                subprocess.Popen([exe], cwd=str(ROOT), stdout=out, stderr=out, stdin=subprocess.DEVNULL, start_new_session=True)
        return True, 'started (claim link will appear in playit log on first run)'
    except Exception as e:
        return False, f'failed: {e}'


def _stop_playit() -> tuple[bool, str]:
    procs: list[psutil.Process] = []
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmd = ' '.join(proc.info.get('cmdline') or []).lower()
            if 'playit' in name or 'playit' in cmd:
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not procs:
        return True, 'not running'
    n = _terminate_processes(procs)
    return True, f'stopped {n} process(es)'


def cmd_help(_: argparse.Namespace) -> int:
    print('ARX command help\n')
    print('  arx help                    Show this help menu')
    print('  arx start [target]          Start services (all|dashboard|ollama|server); default all')
    print('  arx stop                    Stop dashboard + minecraft (keeps ollama running)')
    print('  arx shutdown                Stop dashboard + minecraft + ollama (+playit if running)')
    print('  arx restart                 Restart dashboard + minecraft (keeps ollama policy of start)')
    print('  arx status                  Show status of dashboard/server/ollama/playit')
    print('  arx open                    Open dashboard in default browser')
    print('  arx logs [target]           Show logs (dashboard|server|ollama|playit), default dashboard')
    print('  arx ai set-context <tokens> Set Ollama context tokens (recommended 2048..8192)')
    print('  arx tunnel setup [--url <addr>] [--enable]  Start Playit tunnel + save URL')
    print('  arx tunnel status           Show Playit tunnel status + configured URL')
    print('  arx tunnel open             Open configured Playit address or playit.gg')
    print('  arx tunnel stop             Stop Playit tunnel agent')
    print('  arx version                 Show ARX CLI version')
    print('')
    print('examples:')
    print('  arx start                   # backward-compatible: starts all services')
    print('  arx start dashboard         # only start dashboard')
    print('  arx start ollama            # only start ollama')
    print('  arx start server            # only start minecraft server')
    print('  arx tunnel setup            # launch playit and claim tunnel')
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    dash = bool(_find_dashboard_procs() or _port_open('127.0.0.1', bind_port()))
    server = bool(_find_server_procs())
    ollama = _ollama_ok()
    p_enabled = playit_enabled()
    p_running = _playit_running()
    print(f'dashboard: {"up" if dash else "down"}  ({dashboard_url()})')
    print(f'minecraft: {"up" if server else "down"}  ({minecraft_dir()})')
    print(f'ollama:    {"up" if ollama else "down"}  (http://127.0.0.1:11434)')
    print(f'playit:    {"up" if p_running else "down"}  (enabled={str(p_enabled).lower()}, url={playit_url() or "not-set"})')
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    target = str(getattr(args, 'target', 'all') or 'all').lower()

    if target == 'all':
        ok, msg = _start_ollama()
        print(f'ollama: {msg}')
        if not ok:
            return 1

        ok, msg = _start_server()
        print(f'minecraft: {msg}')
        if not ok:
            return 1

        if playit_enabled():
            ok_p, msg_p = _start_playit()
            print(f'playit: {msg_p}')
            if not ok_p:
                return 1

        ok, msg = _start_dashboard()
        print(f'dashboard: {msg}')
        if not ok:
            return 1

        print(f'open: {dashboard_url()}')
        if os.name == 'nt' and not getattr(args, 'no_open', False):
            try:
                webbrowser.open(dashboard_url())
            except Exception:
                pass
        return 0

    if target == 'dashboard':
        ok, msg = _start_dashboard()
        print(f'dashboard: {msg}')
        if ok:
            print(f'open: {dashboard_url()}')
            if os.name == 'nt' and not getattr(args, 'no_open', False):
                try:
                    webbrowser.open(dashboard_url())
                except Exception:
                    pass
        return 0 if ok else 1

    if target == 'ollama':
        ok, msg = _start_ollama()
        print(f'ollama: {msg}')
        return 0 if ok else 1

    if target == 'server':
        ok, msg = _start_server()
        print(f'minecraft: {msg}')
        return 0 if ok else 1

    print(f'unknown start target: {target} (use all|dashboard|ollama|server)', file=sys.stderr)
    return 1


def cmd_stop(_: argparse.Namespace) -> int:
    ok_d, msg_d = _stop_dashboard()
    ok_s, msg_s = _stop_server()
    print(f'dashboard: {msg_d}')
    print(f'minecraft: {msg_s}')
    # Option A: keep ollama running on stop
    print('ollama: kept running (use "arx shutdown" to stop all)')
    if playit_enabled():
        print('playit: left running (use "arx tunnel stop" or "arx shutdown" to stop tunnel)')

    if not ok_s and os.name == 'nt':
        print('hint: this usually means javaw.exe was started by elevated context. Open PowerShell as Administrator and retry.')

    return 0 if (ok_d and ok_s) else 1


def cmd_shutdown(_: argparse.Namespace) -> int:
    _ = cmd_stop(argparse.Namespace())
    ok_o, msg_o = _stop_ollama()
    print(f'ollama: {msg_o}')
    ok_p, msg_p = _stop_playit()
    print(f'playit: {msg_p}')
    return 0 if (ok_o and ok_p) else 1


def cmd_restart(_: argparse.Namespace) -> int:
    _ = cmd_stop(argparse.Namespace())
    time.sleep(1)
    return cmd_start(argparse.Namespace())


def cmd_open(_: argparse.Namespace) -> int:
    url = dashboard_url()
    print(f'opening {url}')
    webbrowser.open(url)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    target = (args.target or 'dashboard').lower()
    lines = max(1, int(args.lines or 120))

    if target == 'dashboard':
        path = STATE_DIR / 'dashboard.log'
    elif target == 'server':
        path = minecraft_dir() / 'logs' / 'latest.log'
    elif target == 'ollama':
        p1 = STATE_DIR / 'ollama.log'
        p2 = Path('/tmp/arx-ollama.log')
        path = p1 if p1.exists() else p2
    elif target == 'playit':
        path = STATE_DIR / 'playit.log'
    else:
        print('unknown target; use dashboard|server|ollama|playit', file=sys.stderr)
        return 1

    print(_tail(path, lines))
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print('arx-cli v0.1.0')
    return 0


def cmd_ai(args: argparse.Namespace) -> int:
    action = str(getattr(args, 'action', 'help') or 'help').lower()

    if action == 'set-context':
        raw = str(getattr(args, 'tokens', '') or '').strip()
        if not raw.isdigit():
            print('tokens must be numeric, e.g. arx ai set-context 4096', file=sys.stderr)
            return 1
        tokens = int(raw)
        if tokens < 1024 or tokens > 32768:
            print('tokens must be between 1024 and 32768 for stable local runtime', file=sys.stderr)
            return 1

        _set_env_key('GEMMA_CONTEXT_SIZE', str(tokens))
        _set_runtime_context_in_state(tokens)
        print(f'GEMMA_CONTEXT_SIZE set to {tokens}')
        print('restart dashboard to apply: arx restart')
        return 0

    print('usage: arx ai set-context <tokens>')
    return 1


def cmd_tunnel(args: argparse.Namespace) -> int:
    action = str(getattr(args, 'action', 'status') or 'status').lower()

    if action == 'status':
        running = _playit_running()
        print(f'playit: {"up" if running else "down"}')
        print(f'configured: enabled={str(playit_enabled()).lower()} url={playit_url() or "not-set"}')
        if not running:
            print('tip: run "arx tunnel setup" to start playit agent')
        else:
            print('tip: run "arx tunnel open" to open the configured address')
        return 0

    if action == 'setup':
        used_url_flag = bool(getattr(args, 'url', ''))
        if getattr(args, 'enable', False):
            _set_env_key('PLAYIT_ENABLED', 'true')
        if used_url_flag:
            _set_env_key('PLAYIT_URL', str(args.url).strip())

        ok, msg = _start_playit()
        print(f'playit: {msg}')
        print('Playit setup guide:')
        print('  1) Open https://playit.gg and sign in')
        print('  2) Claim this local agent (if prompted)')
        print('  3) Create a TCP tunnel targeting 127.0.0.1:25565')
        print('  4) Copy your public address (example: your-name.playit.gg:12345)')
        print('  5) Save it locally with: arx tunnel setup --url <address> --enable')
        if used_url_flag:
            print(f'current configured public address: {playit_url() or str(args.url).strip()}')
        return 0 if ok else 1

    if action == 'open':
        url = playit_url().strip()
        if url:
            if not (url.startswith('http://') or url.startswith('https://')):
                url = f'http://{url}'
            print(f'opening {url}')
            webbrowser.open(url)
        else:
            print('opening https://playit.gg')
            webbrowser.open('https://playit.gg')
        return 0

    if action == 'stop':
        ok, msg = _stop_playit()
        print(f'playit: {msg}')
        return 0 if ok else 1

    print('unknown tunnel action; use setup|status|open|stop', file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='arx', add_help=False)
    sp = p.add_subparsers(dest='command')

    sp.add_parser('help')
    start_p = sp.add_parser('start')
    start_p.add_argument(
        'target',
        nargs='?',
        default='all',
        choices=('all', 'dashboard', 'ollama', 'server'),
        help='Service target to start (default: all)',
    )
    start_p.add_argument('--no-open', action='store_true', help='Do not auto-open dashboard browser on Windows when starting dashboard/all')
    sp.add_parser('stop')
    sp.add_parser('shutdown')
    sp.add_parser('restart')
    sp.add_parser('status')
    sp.add_parser('open')

    lp = sp.add_parser('logs')
    lp.add_argument('target', nargs='?', default='dashboard')
    lp.add_argument('--lines', type=int, default=120)

    tp = sp.add_parser('tunnel')
    tp.add_argument('action', nargs='?', default='status', choices=('setup', 'status', 'open', 'stop'))
    tp.add_argument('--url', default='', help='Set/update PLAYIT_URL during tunnel setup')
    tp.add_argument('--enable', action='store_true', help='Set PLAYIT_ENABLED=true during tunnel setup')

    ap = sp.add_parser('ai')
    ap.add_argument('action', nargs='?', choices=('set-context',), default='set-context')
    ap.add_argument('tokens', nargs='?')

    sp.add_parser('version')
    sp.add_parser('--help')
    sp.add_parser('-h')
    return p


def main() -> int:
    parser = build_parser()
    if len(sys.argv) == 1:
        return cmd_help(argparse.Namespace())
    args = parser.parse_args()
    cmd = args.command

    table = {
        'help': cmd_help,
        '--help': cmd_help,
        '-h': cmd_help,
        'start': cmd_start,
        'stop': cmd_stop,
        'shutdown': cmd_shutdown,
        'restart': cmd_restart,
        'status': cmd_status,
        'open': cmd_open,
        'logs': cmd_logs,
        'ai': cmd_ai,
        'tunnel': cmd_tunnel,
        'version': cmd_version,
    }
    fn = table.get(cmd)
    if not fn:
        print(f'unknown command: {cmd}\n', file=sys.stderr)
        return cmd_help(argparse.Namespace())
    return int(fn(args))


if __name__ == '__main__':
    raise SystemExit(main())
