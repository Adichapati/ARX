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

    _last_seen_by_user: dict[str, float] = {}
    _ctx: dict[str, deque] = {}

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
    def _is_blocked(command: str) -> bool:
        c = (command or '').strip()
        for pat in OpAssistService.BLOCKED:
            if re.match(pat, c, flags=re.IGNORECASE):
                return True
        return False

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
        hist = OpAssistService._ctx.setdefault(user.lower(), deque(maxlen=8))
        hist.append({'role': 'user', 'content': msg})

        sys = (
            'You are Gemma Assistant for Minecraft operations. '
            'Return strict JSON only. '
            'Schema: {"type":"chat","say":"..."} OR '
            '{"type":"command","command":"/give Steve stone 1","say":"..."}. '
            f'Current user is {user}. Use exact username, no placeholders. '
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
            return {'type': 'chat', 'say': 'Local Ollama is unavailable. Please start/check Ollama and configured Gemma model.'}
        except Exception:
            return {'type': 'chat', 'say': 'I could not parse model output.'}
        return {'type': 'chat', 'say': 'No valid response.'}

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

                    cmd = str(decision.get('command', '')).strip()
                    if not cmd:
                        OpAssistService._say(f'{user}, no valid command.')
                        continue

                    if OpAssistService._is_blocked(cmd):
                        OpAssistService._say(f'{user}, that command is blocked for safety.')
                        continue

                    if cmd.startswith('/'):
                        cmd = cmd[1:].strip()

                    res = ServerService.send_console_command(cmd, unsafe_ok=True)
                    obs = LogService.wait_for_command_result(cmd, timeout_sec=4.0)

                    if not res.get('ok'):
                        OpAssistService._say(f'{user}, command failed: {res.get("error", "unknown")}')
                        continue

                    follow = OpAssistService._llm_decide(user, f'command issued: {cmd}', obs=obs)
                    OpAssistService._say(str(follow.get('say', f'done {user} -> {cmd}')))

            except Exception:
                pass

            await asyncio.sleep(1.2)
