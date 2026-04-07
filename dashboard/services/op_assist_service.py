import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from collections import deque

from ..config import (
    AGENT_TRIGGER,
    GEMMA_COOLDOWN_SEC,
    GEMMA_ENABLED,
    GEMMA_MAX_REPLY_CHARS,
    GEMMA_OLLAMA_MODEL,
    GEMMA_OLLAMA_URL,
    GEMMA_TEMPERATURE,
    KNOWN_PLAYERS_PATH,
    OP_ASSIST_STATE_PATH,
)
from .config_service import ConfigService
from .log_service import LogService
from .server_service import ServerService


class OpAssistService:
    BLOCKED = [
        r'^/?stop\s*$',
        r'^/?restart\s*$',
        r'^/?deop\s+',
        r'^/?op\s+@',
        r'^/?ban-ip\s+',
        r'.*(?:&&|\|\||;|`|\$\().*',
    ]

    # Strict allowlist templates (Phase 3 safety gate)
    ALLOWLIST = [
        r'^say\s+.+$',
        r'^give\s+[A-Za-z0-9_]{3,16}\s+[a-z0-9_:\.-]+(?:\s+[1-9][0-9]?)?$',
        r'^clear\s+[A-Za-z0-9_]{3,16}(?:\s+[a-z0-9_:\.-]+)?$',
        r'^effect\s+give\s+[A-Za-z0-9_]{3,16}\s+[a-z0-9_:\.-]+(?:\s+[0-9]{1,4})?(?:\s+[0-9]{1,2})?$',
        r'^time\s+set\s+(?:day|night|noon|midnight)$',
        r'^weather\s+(?:clear|rain|thunder)(?:\s+[0-9]{1,5})?$',
        r'^gamemode\s+(?:survival|creative|adventure|spectator)\s+[A-Za-z0-9_]{3,16}$',
        r'^tp\s+[A-Za-z0-9_]{3,16}\s+-?[0-9]{1,5}\s+-?[0-9]{1,5}\s+-?[0-9]{1,5}$',
        r'^whitelist\s+(?:add|remove)\s+[A-Za-z0-9_]{3,16}$',
        r'^whitelist\s+(?:list|reload)$',
    ]

    _last_seen_by_user: dict[str, float] = {}
    _ctx: dict[str, deque] = {}
    _ollama_health_cache = {'ts': 0.0, 'ok': False, 'message': ''}

    @staticmethod
    def _runtime_cfg() -> dict:
        cfg = ConfigService.load_arx_runtime_config()
        return {
            'trigger': str(cfg.get('agent_trigger', AGENT_TRIGGER)).strip().lower() or AGENT_TRIGGER,
            'model': str(cfg.get('gemma_model', GEMMA_OLLAMA_MODEL)).strip() or GEMMA_OLLAMA_MODEL,
            'temperature': float(cfg.get('gemma_temperature', GEMMA_TEMPERATURE)),
            'max_reply_chars': int(cfg.get('gemma_max_reply_chars', GEMMA_MAX_REPLY_CHARS)),
            'cooldown_sec': float(cfg.get('gemma_cooldown_sec', GEMMA_COOLDOWN_SEC)),
        }

    @staticmethod
    def _known_ops() -> set[str]:
        try:
            data = json.loads(KNOWN_PLAYERS_PATH.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return {str(x).lower() for x in data}
        except Exception:
            pass
        return set()

    @staticmethod
    def _load_offset() -> int:
        try:
            data = json.loads(OP_ASSIST_STATE_PATH.read_text(encoding='utf-8'))
            return int(data.get('log_offset', 0) or 0)
        except Exception:
            return 0

    @staticmethod
    def _save_offset(offset: int) -> None:
        OP_ASSIST_STATE_PATH.write_text(json.dumps({'log_offset': int(offset)}, indent=2), encoding='utf-8')

    @staticmethod
    def _normalize_command(command: str) -> str:
        cmd = (command or '').strip()
        if cmd.startswith('/'):
            cmd = cmd[1:]
        cmd = re.sub(r'\s+', ' ', cmd).strip()
        return cmd

    @staticmethod
    def _contains_placeholder(command: str) -> bool:
        c = command.lower()
        placeholder_markers = [
            '<player',
            '<username',
            '{player',
            '{username',
            '[player',
            '[username',
            'playername',
            'your_username',
        ]
        if any(x in c for x in placeholder_markers):
            return True
        if re.search(r'<[^>]+>', command) or re.search(r'\{[^}]+\}', command):
            return True
        return False

    @staticmethod
    def _is_blocked(command: str) -> bool:
        c = (command or '').strip()
        for pat in OpAssistService.BLOCKED:
            if re.match(pat, c, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _is_allowlisted(command: str) -> bool:
        c = command.strip()
        for pat in OpAssistService.ALLOWLIST:
            if re.match(pat, c, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _target_must_match_user(command: str, user: str) -> bool:
        """Require identity match for player-targeted commands."""
        c = command.strip()
        u = user.lower()

        # give <user> ...
        m = re.match(r'^give\s+([A-Za-z0-9_]{3,16})\s+', c, flags=re.IGNORECASE)
        if m and m.group(1).lower() != u:
            return False

        # clear <user> ...
        m = re.match(r'^clear\s+([A-Za-z0-9_]{3,16})(?:\s+|$)', c, flags=re.IGNORECASE)
        if m and m.group(1).lower() != u:
            return False

        # effect give <user> ...
        m = re.match(r'^effect\s+give\s+([A-Za-z0-9_]{3,16})\s+', c, flags=re.IGNORECASE)
        if m and m.group(1).lower() != u:
            return False

        # gamemode <mode> <user>
        m = re.match(r'^gamemode\s+(?:survival|creative|adventure|spectator)\s+([A-Za-z0-9_]{3,16})$', c, flags=re.IGNORECASE)
        if m and m.group(1).lower() != u:
            return False

        # tp <user> x y z
        m = re.match(r'^tp\s+([A-Za-z0-9_]{3,16})\s+-?[0-9]{1,5}\s+-?[0-9]{1,5}\s+-?[0-9]{1,5}$', c, flags=re.IGNORECASE)
        if m and m.group(1).lower() != u:
            return False

        return True

    @staticmethod
    def _ollama_health(cfg_model: str) -> tuple[bool, str]:
        now = time.time()
        cached = OpAssistService._ollama_health_cache
        if now - float(cached.get('ts', 0.0)) < 6.0:
            return bool(cached.get('ok')), str(cached.get('message', ''))

        try:
            req = urllib.request.Request('http://127.0.0.1:11434/api/tags', method='GET')
            with urllib.request.urlopen(req, timeout=1.5) as r:
                raw = r.read().decode('utf-8', errors='replace')
            data = json.loads(raw)
            models = data.get('models') or []
            names = {str(m.get('name', '')).strip() for m in models if isinstance(m, dict)}
            if cfg_model not in names:
                msg = f"Model '{cfg_model}' is not pulled. Run: ollama pull {cfg_model}"
                OpAssistService._ollama_health_cache = {'ts': now, 'ok': False, 'message': msg}
                return False, msg
            OpAssistService._ollama_health_cache = {'ts': now, 'ok': True, 'message': 'ok'}
            return True, 'ok'
        except Exception:
            msg = 'Ollama is unavailable. Start with: ollama serve'
            OpAssistService._ollama_health_cache = {'ts': now, 'ok': False, 'message': msg}
            return False, msg

    @staticmethod
    def _say(text: str):
        text = (text or '').strip()
        if not text:
            return
        max_reply = OpAssistService._runtime_cfg()['max_reply_chars']
        if len(text) > max_reply:
            text = text[: max_reply - 1] + '…'
        ServerService.send_console_command(f'say Gemma: {text}', unsafe_ok=True)

    @staticmethod
    def _route_non_op(user: str, msg: str) -> dict:
        return {'type': 'chat', 'say': f"{user}, operator command mode is available to server OPs only."}

    @staticmethod
    def _llm_decide(user: str, msg: str, obs: str = '') -> dict:
        if not GEMMA_ENABLED:
            return {'type': 'chat', 'say': 'Gemma assistant is disabled in local config.'}

        cfg = OpAssistService._runtime_cfg()
        ok, health_msg = OpAssistService._ollama_health(cfg['model'])
        if not ok:
            return {'type': 'chat', 'say': health_msg}

        hist = OpAssistService._ctx.setdefault(user.lower(), deque(maxlen=8))
        hist.append({'role': 'user', 'content': msg})

        sys = (
            'You are Gemma Assistant for Minecraft operations. '
            'Return strict JSON only. '
            'Schema: {"type":"chat","say":"..."} OR '
            '{"type":"command","command":"...","say":"..."}. '
            f'Current user is {user}. Use exact username and no placeholders. '
            'Allowed commands only: '
            'say, give <user> <item> [count], clear <user> [item], effect give <user> <effect> [seconds] [amplifier], '
            'time set day|night|noon|midnight, weather clear|rain|thunder [duration], '
            'gamemode <mode> <user>, tp <user> x y z, whitelist add/remove/list/reload. '
            'For player-targeted commands, target must be the requesting user. '
            'Never output shell commands. Keep responses concise.'
        )

        messages = [{'role': 'system', 'content': sys}] + list(hist)
        if obs:
            messages.append({'role': 'user', 'content': f'Observation: {obs}'})

        payload = {
            'model': cfg['model'],
            'messages': messages,
            'temperature': cfg['temperature'],
        }

        req = urllib.request.Request(
            GEMMA_OLLAMA_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read().decode('utf-8', errors='replace')
            data = json.loads(raw)
            content = data['choices'][0]['message']['content']
            content = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.IGNORECASE)
            content = re.sub(r'\s*```$', '', content.strip())
            obj = json.loads(content)
            if isinstance(obj, dict) and obj.get('type') in ('chat', 'command'):
                if 'say' in obj:
                    hist.append({'role': 'assistant', 'content': str(obj.get('say', ''))})
                return obj
        except (urllib.error.URLError, urllib.error.HTTPError):
            return {'type': 'chat', 'say': 'Local Ollama is unavailable. Start Ollama and ensure configured model is pulled.'}
        except Exception:
            return {'type': 'chat', 'say': 'I could not parse model output.'}
        return {'type': 'chat', 'say': 'No valid response.'}

    @staticmethod
    def _observation_indicates_failure(obs: str) -> bool:
        text = (obs or '').lower()
        bad = ['unknown or incomplete command', 'error', 'failed', 'exception']
        return any(x in text for x in bad)

    @staticmethod
    async def run_loop():
        offset = OpAssistService._load_offset()
        while True:
            try:
                d = LogService.diff_from(offset, max_bytes=131072)
                offset = d['next_offset']
                OpAssistService._save_offset(offset)
                events = LogService.extract_chat_events(d['chunk'])
                if not events:
                    await asyncio.sleep(1.5)
                    continue

                known_ops = OpAssistService._known_ops()
                cfg = OpAssistService._runtime_cfg()
                now = time.time()

                for ev in events:
                    user = ev['user']
                    msg = ev['message']
                    if cfg['trigger'] not in msg.lower():
                        continue

                    last = OpAssistService._last_seen_by_user.get(user.lower(), 0.0)
                    if now - last < cfg['cooldown_sec']:
                        continue
                    OpAssistService._last_seen_by_user[user.lower()] = now

                    if user.lower() not in known_ops:
                        decision = OpAssistService._route_non_op(user, msg)
                        OpAssistService._say(str(decision.get('say', '')))
                        continue

                    decision = OpAssistService._llm_decide(user, msg)
                    if decision.get('type') != 'command':
                        OpAssistService._say(str(decision.get('say', f'Hi {user}')))
                        continue

                    cmd = OpAssistService._normalize_command(str(decision.get('command', '')))
                    if not cmd:
                        OpAssistService._say(f'{user}, no valid command.')
                        continue

                    # Placeholder guard
                    if OpAssistService._contains_placeholder(cmd):
                        OpAssistService._say(f'{user}, unresolved placeholder detected. Command refused.')
                        continue

                    # Denylist guard
                    if OpAssistService._is_blocked(cmd):
                        OpAssistService._say(f'{user}, that command is blocked for safety.')
                        continue

                    # Allowlist guard
                    if not OpAssistService._is_allowlisted(cmd):
                        OpAssistService._say(f'{user}, command is outside the allowlist and was refused.')
                        continue

                    # Identity match guard for targeted commands
                    if not OpAssistService._target_must_match_user(cmd, user):
                        OpAssistService._say(f'{user}, targeted command must use your own username.')
                        continue

                    res = ServerService.send_console_command(cmd, unsafe_ok=True)
                    obs = LogService.wait_for_command_result(cmd, timeout_sec=4.5)

                    if not res.get('ok'):
                        OpAssistService._say(f'{user}, command failed: {res.get("error", "unknown")}')
                        continue

                    if not obs:
                        OpAssistService._say(f'{user}, command was sent but no confirmation was observed yet.')
                        continue

                    if OpAssistService._observation_indicates_failure(obs):
                        OpAssistService._say(f'{user}, command appears to have failed. Check logs.')
                        continue

                    follow = OpAssistService._llm_decide(user, f'command issued: {cmd}', obs=obs)
                    OpAssistService._say(str(follow.get('say', f'{user}, confirmed: {cmd}')))

            except Exception:
                pass

            await asyncio.sleep(1.2)
