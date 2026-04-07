import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

APP_NAME = 'ARX — Agentic Runtime for eXecution'
BIND_HOST = os.environ.get('BIND_HOST', '0.0.0.0')
# Isolation default: do NOT reuse existing dashboard port.
BIND_PORT = int(os.environ.get('BIND_PORT', '18890'))

MINECRAFT_DIR = (ROOT / 'app' / 'minecraft_server').resolve()
LOG_FILE = MINECRAFT_DIR / 'logs' / 'latest.log'
SERVER_PROPERTIES_PATH = MINECRAFT_DIR / 'server.properties'
EULA_PATH = MINECRAFT_DIR / 'eula.txt'
SERVER_JAR = MINECRAFT_DIR / 'server.jar'

STATE_DIR = (ROOT / 'state').resolve()
KNOWN_PLAYERS_PATH = STATE_DIR / 'known_players.json'
OP_ASSIST_STATE_PATH = STATE_DIR / 'op_assist_state.json'

AUTH_USERNAME = os.environ.get('AUTH_USERNAME', 'admin')
AUTH_PASSWORD_HASH = os.environ.get('AUTH_PASSWORD_HASH', '')
SESSION_SECRET = os.environ.get('SESSION_SECRET', secrets.token_urlsafe(32))

PUBLIC_READ_ENABLED = os.environ.get('PUBLIC_READ_ENABLED', 'false').lower() == 'true'
PUBLIC_READ_TOKEN = os.environ.get('PUBLIC_READ_TOKEN', secrets.token_urlsafe(24))

MC_HOST = os.environ.get('MC_HOST', '127.0.0.1')
MC_PORT = int(os.environ.get('MC_PORT', '25565'))
TMUX_SESSION = os.environ.get('MC_TMUX_SESSION', 'mc_server_arx')

# Gemma-only public config surface
GEMMA_ENABLED = os.environ.get('GEMMA_ENABLED', 'true').lower() == 'true'
GEMMA_OLLAMA_URL = os.environ.get('GEMMA_OLLAMA_URL', 'http://localhost:11434/v1/chat/completions')
GEMMA_OLLAMA_MODEL = os.environ.get('GEMMA_OLLAMA_MODEL', 'gemma4:e2b')
GEMMA_MAX_REPLY_CHARS = int(os.environ.get('GEMMA_MAX_REPLY_CHARS', '220'))
GEMMA_COOLDOWN_SEC = float(os.environ.get('GEMMA_COOLDOWN_SEC', '2.5'))
AGENT_TRIGGER = os.environ.get('AGENT_TRIGGER', 'gemma').strip().lower() or 'gemma'

# First-run tuning placeholders (phase 4 UI setup)
GEMMA_CONTEXT_SIZE = int(os.environ.get('GEMMA_CONTEXT_SIZE', '8192'))
GEMMA_TEMPERATURE = float(os.environ.get('GEMMA_TEMPERATURE', '0.2'))

MAX_ATTEMPTS = int(os.environ.get('MAX_ATTEMPTS', '5'))
ATTEMPT_WINDOW_SEC = int(os.environ.get('ATTEMPT_WINDOW_SEC', '300'))
LOCKOUT_SEC = int(os.environ.get('LOCKOUT_SEC', '900'))

_attempts: Dict[str, Deque[float]] = defaultdict(deque)
_lockouts: Dict[str, float] = {}
_ws_tickets: Dict[str, float] = {}

state: Dict[str, Any] = {
    'last_action': 'none',
    'last_status_note': 'ARX dashboard started',
    'running': False,
}

_cache: Dict[str, Any] = {
    'snapshot': None,
    'updated_at': 0.0,
}

_console_history: Deque[str] = deque(maxlen=200)


def now_ts() -> float:
    return time.time()


def ensure_dirs() -> None:
    (MINECRAFT_DIR / 'logs').mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not KNOWN_PLAYERS_PATH.exists():
        KNOWN_PLAYERS_PATH.write_text('[]\n', encoding='utf-8')
    if not OP_ASSIST_STATE_PATH.exists():
        OP_ASSIST_STATE_PATH.write_text('{"log_offset": 0}\n', encoding='utf-8')
    if not LOG_FILE.exists():
        LOG_FILE.touch()
