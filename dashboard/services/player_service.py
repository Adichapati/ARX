import json
from pathlib import Path

from ..config import KNOWN_PLAYERS_PATH, STATE_DIR
from .server_service import ServerService

WHITELIST_PATH = STATE_DIR / 'whitelist_players.json'


class PlayerService:
    @staticmethod
    def _validate_username(name: str) -> str:
        n = str(name or '').strip()
        if not (3 <= len(n) <= 16):
            raise ValueError('username must be 3..16 chars')
        allowed = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
        if any(c not in allowed for c in n):
            raise ValueError('username must contain only [A-Za-z0-9_]')
        return n

    @staticmethod
    def _read_list(path: Path) -> list[str]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                vals = []
                for x in data:
                    s = str(x).strip()
                    if s:
                        vals.append(s)
                return vals
        except Exception:
            pass
        return []

    @staticmethod
    def _write_list(path: Path, values: list[str]) -> list[str]:
        seen = set()
        out = []
        for v in values:
            s = str(v).strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(out, key=str.lower), indent=2), encoding='utf-8')
        return sorted(out, key=str.lower)

    @staticmethod
    def get_ops() -> list[str]:
        return PlayerService._read_list(KNOWN_PLAYERS_PATH)

    @staticmethod
    def get_whitelist() -> list[str]:
        return PlayerService._read_list(WHITELIST_PATH)

    @staticmethod
    def add_op(username: str, sync_runtime: bool = True) -> list[str]:
        u = PlayerService._validate_username(username)
        cur = PlayerService.get_ops()
        if u.lower() not in {x.lower() for x in cur}:
            cur.append(u)
        saved = PlayerService._write_list(KNOWN_PLAYERS_PATH, cur)
        if sync_runtime and ServerService.tmux_session_exists():
            ServerService.send_console_command(f'op {u}', unsafe_ok=True)
        return saved

    @staticmethod
    def remove_op(username: str, sync_runtime: bool = True) -> list[str]:
        u = PlayerService._validate_username(username)
        cur = [x for x in PlayerService.get_ops() if x.lower() != u.lower()]
        saved = PlayerService._write_list(KNOWN_PLAYERS_PATH, cur)
        if sync_runtime and ServerService.tmux_session_exists():
            ServerService.send_console_command(f'deop {u}', unsafe_ok=True)
        return saved

    @staticmethod
    def add_whitelist(username: str, sync_runtime: bool = True) -> list[str]:
        u = PlayerService._validate_username(username)
        cur = PlayerService.get_whitelist()
        if u.lower() not in {x.lower() for x in cur}:
            cur.append(u)
        saved = PlayerService._write_list(WHITELIST_PATH, cur)
        if sync_runtime and ServerService.tmux_session_exists():
            ServerService.send_console_command(f'whitelist add {u}', unsafe_ok=True)
        return saved

    @staticmethod
    def remove_whitelist(username: str, sync_runtime: bool = True) -> list[str]:
        u = PlayerService._validate_username(username)
        cur = [x for x in PlayerService.get_whitelist() if x.lower() != u.lower()]
        saved = PlayerService._write_list(WHITELIST_PATH, cur)
        if sync_runtime and ServerService.tmux_session_exists():
            ServerService.send_console_command(f'whitelist remove {u}', unsafe_ok=True)
        return saved

    @staticmethod
    def snapshot() -> dict:
        q = ServerService.mc_query()
        return {
            'ops': PlayerService.get_ops(),
            'whitelist': PlayerService.get_whitelist(),
            'online': q.get('player_names', []) if q.get('online') else [],
        }
