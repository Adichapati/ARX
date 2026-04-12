import json
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


APP_NAME = 'ARX Minecraft Dashboard'


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


# Security-hardening default: bind only to localhost unless explicitly overridden.
BIND_HOST = os.environ.get('BIND_HOST', '127.0.0.1').strip() or '127.0.0.1'
BIND_PORT = _env_int('BIND_PORT', 18890)

MINECRAFT_DIR = Path(os.environ.get('MINECRAFT_DIR', str((ROOT / 'app' / 'minecraft_server').resolve()))).resolve()
LOG_FILE = MINECRAFT_DIR / 'logs/latest.log'
SERVER_PROPERTIES_PATH = MINECRAFT_DIR / 'server.properties'
OPS_FILE = MINECRAFT_DIR / 'ops.json'
WHITELIST_FILE = MINECRAFT_DIR / 'whitelist.json'
BANNED_PLAYERS_FILE = MINECRAFT_DIR / 'banned-players.json'
BACKUPS_DIR = MINECRAFT_DIR / 'backups'

DATA_DIR = Path(os.environ.get('DATA_DIR', str((ROOT / 'state').resolve())))
SCHEDULES_PATH = DATA_DIR / 'schedules.json'
PLUGINS_DIR = DATA_DIR / 'plugin_staging'
PLUGINS_INDEX_PATH = DATA_DIR / 'plugins-staged.json'
KNOWN_PLAYERS_PATH = DATA_DIR / 'known_players.json'
JOIN_WATCH_STATE_PATH = DATA_DIR / 'join_watch_state.json'
OP_ASSIST_STATE_PATH = DATA_DIR / 'op_assist_state.json'
AUTH_LOCKOUTS_PATH = DATA_DIR / 'auth_lockouts.json'

MC_HOST = os.environ.get('MC_HOST', '127.0.0.1')
MC_PORT = _env_int('MC_PORT', 25565)
TMUX_SESSION = os.environ.get('MC_TMUX_SESSION', 'mc_server_arx')
RCON_HOST = os.environ.get('RCON_HOST', '127.0.0.1')
RCON_PORT = _env_int('RCON_PORT', 25575)
RCON_PASSWORD = (os.environ.get('RCON_PASSWORD', '') or '').strip() or secrets.token_urlsafe(24)

AUTH_USERNAME = os.environ.get('AUTH_USERNAME', 'admin')
AUTH_PASSWORD_HASH = os.environ.get('AUTH_PASSWORD_HASH', '')
AUTH_GUEST_USERNAME = os.environ.get('AUTH_GUEST_USERNAME', 'guest')
AUTH_GUEST_PASSWORD_HASH = os.environ.get('AUTH_GUEST_PASSWORD_HASH', '')
SESSION_SECRET = os.environ.get('SESSION_SECRET', secrets.token_urlsafe(32))
PUBLIC_READ_ENABLED = _env_bool('PUBLIC_READ_ENABLED', False)
PUBLIC_READ_TOKEN = (os.environ.get('PUBLIC_READ_TOKEN', '') or '').strip() or secrets.token_urlsafe(24)

# Session/CSRF controls
SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', False)
SESSION_COOKIE_SAMESITE = (os.environ.get('SESSION_COOKIE_SAMESITE', 'lax') or 'lax').strip().lower()
if SESSION_COOKIE_SAMESITE not in {'lax', 'strict', 'none'}:
    SESSION_COOKIE_SAMESITE = 'lax'
CSRF_ENABLED = _env_bool('CSRF_ENABLED', True)
TRUST_X_FORWARDED_FOR = _env_bool('TRUST_X_FORWARDED_FOR', False)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Legacy Wilson envs retained for full old-dashboard feature parity
WILSON_AI_ENABLED = _env_bool('WILSON_AI_ENABLED', True)
WILSON_AI_PROVIDER = os.environ.get('WILSON_AI_PROVIDER', 'copilot')
WILSON_AI_BASE_URL = os.environ.get('WILSON_AI_BASE_URL', 'https://api.githubcopilot.com/chat/completions')
WILSON_AI_MODEL = os.environ.get('WILSON_AI_MODEL', 'gpt-4o-mini')
WILSON_AI_TOKEN = os.environ.get('WILSON_AI_TOKEN', os.environ.get('COPILOT_GITHUB_TOKEN', ''))
WILSON_OP_COOLDOWN_SEC = float(os.environ.get('WILSON_OP_COOLDOWN_SEC', '2.5'))
WILSON_CONFIRM_TTL_SEC = _env_int('WILSON_CONFIRM_TTL_SEC', 45)
WILSON_MAX_REPLY_CHARS = _env_int('WILSON_MAX_REPLY_CHARS', 220)

# Gemma assistant runtime config (preferred names)
AGENT_TRIGGER = os.environ.get('AGENT_TRIGGER', 'gemma').strip().lower() or 'gemma'
GEMMA_ENABLED = _env_bool('GEMMA_ENABLED', WILSON_AI_ENABLED)
GEMMA_OLLAMA_URL = os.environ.get('GEMMA_OLLAMA_URL', os.environ.get('WILSON_AI_BASE_URL', 'http://localhost:11434/v1/chat/completions'))
GEMMA_OLLAMA_MODEL = os.environ.get('GEMMA_OLLAMA_MODEL', os.environ.get('WILSON_AI_MODEL', 'gemma4:e2b'))
GEMMA_CONTEXT_SIZE = _env_int('GEMMA_CONTEXT_SIZE', 8192)
GEMMA_TEMPERATURE = float(os.environ.get('GEMMA_TEMPERATURE', '0.2'))
GEMMA_COOLDOWN_SEC = float(os.environ.get('GEMMA_COOLDOWN_SEC', os.environ.get('WILSON_OP_COOLDOWN_SEC', '2.5')))
GEMMA_MAX_REPLY_CHARS = _env_int('GEMMA_MAX_REPLY_CHARS', WILSON_MAX_REPLY_CHARS)
# Beta safety gate: command execution allowed only when explicitly enabled.
GEMMA_COMMAND_EXECUTION_BETA = _env_bool('GEMMA_COMMAND_EXECUTION_BETA', True)

PLAYIT_ENABLED = _env_bool('PLAYIT_ENABLED', False)
PLAYIT_URL = os.environ.get('PLAYIT_URL', '').strip()

MAX_ATTEMPTS = 5
ATTEMPT_WINDOW_SEC = 300
LOCKOUT_SEC = 900
_attempts: Dict[str, Deque[float]] = defaultdict(deque)
_lockouts: Dict[str, float] = {}

_ws_tickets: Dict[str, float] = {}

state: Dict[str, Any] = {
    'auto_start': False,
    'auto_stop': True,
    'last_action': 'none',
    'last_status_note': 'dashboard started',
    'no_player_since': None,
    'rcon_last_ok_at': 0.0,
}

_cache: Dict[str, Any] = {
    'snapshot': None,
    'logs': 'No logs yet.',
    'updated_at': 0.0,
}

_metrics_hist: Deque[Dict[str, float]] = deque(maxlen=180)
_player_hist: Deque[Dict[str, float]] = deque(maxlen=180)
_public_ip_cache = {'value': '127.0.0.1', 'expires_at': 0.0}
_console_history: Deque[str] = deque(maxlen=200)

_scheduler: Dict[str, Any] = {
    'restart_minutes': 0,
    'backup_minutes': 0,
    'last_restart_at': 0.0,
    'last_backup_at': 0.0,
}

_console_policy: Dict[str, Any] = {
    'tier': 'safe',  # safe | moderate | admin
}


def now_ts() -> float:
    return time.time()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)


def load_scheduler() -> None:
    if not SCHEDULES_PATH.exists():
        return
    try:
        data = json.loads(SCHEDULES_PATH.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            _scheduler.update({
                'restart_minutes': int(data.get('restart_minutes', 0) or 0),
                'backup_minutes': int(data.get('backup_minutes', 0) or 0),
                'last_restart_at': float(data.get('last_restart_at', 0) or 0),
                'last_backup_at': float(data.get('last_backup_at', 0) or 0),
            })
    except Exception:
        pass


def save_scheduler() -> None:
    SCHEDULES_PATH.write_text(json.dumps(_scheduler, indent=2), encoding='utf-8')


def load_lockouts() -> None:
    _lockouts.clear()
    if not AUTH_LOCKOUTS_PATH.exists():
        return
    try:
        data = json.loads(AUTH_LOCKOUTS_PATH.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return
        now = now_ts()
        for key, val in data.items():
            try:
                until = float(val)
            except Exception:
                continue
            if until > now and isinstance(key, str) and key:
                _lockouts[key] = until
    except Exception:
        pass


def save_lockouts() -> None:
    try:
        now = now_ts()
        live = {k: float(v) for k, v in _lockouts.items() if float(v) > now}
        AUTH_LOCKOUTS_PATH.write_text(json.dumps(live, indent=2), encoding='utf-8')
    except Exception:
        pass


def load_plugins_index() -> list[dict]:
    if not PLUGINS_INDEX_PATH.exists():
        return []
    try:
        data = json.loads(PLUGINS_INDEX_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_plugins_index(items: list[dict]) -> None:
    PLUGINS_INDEX_PATH.write_text(json.dumps(items, indent=2), encoding='utf-8')


def load_known_players() -> list[str]:
    if not KNOWN_PLAYERS_PATH.exists():
        return []
    try:
        data = json.loads(KNOWN_PLAYERS_PATH.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except Exception:
        pass
    return []


def save_known_players(players: list[str]) -> None:
    KNOWN_PLAYERS_PATH.write_text(json.dumps(sorted(set(players)), indent=2), encoding='utf-8')


def load_join_watch_state() -> dict:
    if not JOIN_WATCH_STATE_PATH.exists():
        return {'log_offset': 0}
    try:
        data = json.loads(JOIN_WATCH_STATE_PATH.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return {'log_offset': int(data.get('log_offset', 0) or 0)}
    except Exception:
        pass
    return {'log_offset': 0}


def save_join_watch_state(state: dict) -> None:
    JOIN_WATCH_STATE_PATH.write_text(json.dumps({'log_offset': int(state.get('log_offset', 0) or 0)}, indent=2), encoding='utf-8')


def load_op_assist_state() -> dict:
    if not OP_ASSIST_STATE_PATH.exists():
        return {'log_offset': 0}
    try:
        data = json.loads(OP_ASSIST_STATE_PATH.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return {'log_offset': int(data.get('log_offset', 0) or 0)}
    except Exception:
        pass
    return {'log_offset': 0}


def save_op_assist_state(state: dict) -> None:
    OP_ASSIST_STATE_PATH.write_text(json.dumps({'log_offset': int(state.get('log_offset', 0) or 0)}, indent=2), encoding='utf-8')
