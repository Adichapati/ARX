import asyncio
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from ..config import (
    AGENT_TRIGGER,
    GEMMA_COMMAND_EXECUTION_BETA,
    GEMMA_CONTEXT_SIZE,
    GEMMA_COOLDOWN_SEC,
    GEMMA_ENABLED,
    GEMMA_MAX_REPLY_CHARS,
    GEMMA_OLLAMA_MODEL,
    GEMMA_OLLAMA_URL,
    GEMMA_TEMPERATURE,
    LOG_FILE,
    load_op_assist_state,
    save_op_assist_state,
)
from .player_service import PlayerService
from .server_service import ServerService

CHAT_RE = re.compile(r"\]:\s*(?:\[[^\]]+\]\s*)?<([A-Za-z0-9_]{3,16})>\s*(.+)$")
# Some server/proxy stacks emit chat as "name: message" instead of "<name> message".
CHAT_RE_COLON = re.compile(r"\]:\s*(?:\[[^\]]+\]\s*)?([A-Za-z0-9_]{3,16})\s*:\s*(.+)$")
SKILL_MD_PATH = Path(__file__).resolve().parents[2] / 'prompts' / 'gemma-minecraft-commands.md'


class OpAssistService:
    BLOCKED_CMD_PATTERNS = [
        r'^stop\s*$',
        r'^restart\s*$',
        r'^reload\s*$',
        r'^save-off\s*$',
        r'^op\s+',
        r'^deop\s+',
        r'^whitelist\s+off\s*$',
        r'^ban-ip\s+',
        r'^pardon-ip\s+',
        r'^debug\s+',
        r'^perf\s+',
        r'.*\b(?:rm|sudo|chmod|chown|mv|cp)\b.*',
        r'.*(?:&&|\|\||;|`|\$\().*',
        r'.*\b(?:delete\s+world|wipe\s+world|format\s+disk)\b.*',
    ]


    # runtime memory (in-process)
    _last_seen_by_user: dict[str, float] = {}
    _chat_history: dict[str, list[dict]] = {}

    @staticmethod
    def _say(text: str):
        text = (text or '').strip()
        if not text:
            return
        if len(text) > GEMMA_MAX_REPLY_CHARS:
            text = text[:GEMMA_MAX_REPLY_CHARS - 1] + '…'
        ServerService.send_console_command(f"say {AGENT_TRIGGER}: {text}", tier='admin', unsafe_ok=True)

    @staticmethod
    def _is_blocked(cmd: str) -> bool:
        c = (cmd or '').strip()
        for pat in OpAssistService.BLOCKED_CMD_PATTERNS:
            if re.match(pat, c, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _can_execute_commands_for_user(is_op: bool) -> bool:
        return bool(GEMMA_COMMAND_EXECUTION_BETA and is_op)

    @staticmethod
    def _enforce_permissions_on_decision(user: str, decision: dict, can_execute: bool) -> dict:
        if not isinstance(decision, dict):
            return {'type': 'chat', 'say': f"{user}, I couldn't understand that request. Please try again."}

        if decision.get('type') != 'command':
            return decision

        if can_execute:
            return decision

        if GEMMA_COMMAND_EXECUTION_BETA:
            reason = 'command execution is OP-only right now.'
        else:
            reason = 'command execution is currently in beta and disabled.'

        return {
            'type': 'chat',
            'say': f"{user}, I can guide you and answer questions, but {reason}",
        }

    @staticmethod
    def _parse_chat_line(line: str) -> Optional[tuple[str, str]]:
        m = CHAT_RE.search(line)
        if m:
            return m.group(1), m.group(2).strip()
        m = CHAT_RE_COLON.search(line)
        if m:
            return m.group(1), m.group(2).strip()
        return None

    @staticmethod
    def _extract_after_trigger(msg: str) -> str:
        trig = re.escape(AGENT_TRIGGER)
        parts = re.split(rf'\b{trig}\b', msg, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) < 2:
            return ''
        tail = parts[1].strip()
        tail = re.sub(r'^[\s:,.!\-]+', '', tail)
        if tail.startswith('/'):
            tail = tail[1:].strip()
        return tail

    @staticmethod
    def _load_skill_markdown() -> str:
        try:
            if SKILL_MD_PATH.exists():
                txt = SKILL_MD_PATH.read_text(encoding='utf-8', errors='ignore').strip()
                if txt:
                    return txt
        except Exception:
            pass
        return """# Gemma Minecraft Command Style Guide
- Return JSON only.
- For action requests, always use type=command.
- Command must be a single valid Minecraft console command (no slash).
- Never explain limitations; convert request into command.
- Use exact player name where needed.
Examples:
- give item: give <player> minecraft:torch 64
- set day: time set day
- summon dragon on player: execute at <player> run summon minecraft:ender_dragon ~ ~ ~
- kill nearby mobs: execute at <player> run kill @e[type=!minecraft:player,type=!minecraft:item,type=!minecraft:experience_orb,distance=..24]
"""

    @staticmethod
    def _sanitize_command(user: str, cmd: str) -> tuple[Optional[str], Optional[str]]:
        c = (cmd or '').strip().replace('\n', ' ').replace('\r', ' ')
        if not c:
            return None, 'empty command'
        if len(c) > 220:
            return None, 'command too long'

        # Allow kill commands (user requested), only basic structural sanitation applies.

        # Normalize dragon summon to user position.
        if re.match(r'^summon\s+minecraft:ender_dragon\b', c, flags=re.IGNORECASE):
            c = f'execute at {user} run {c}'

        # Normalize give command target/item.
        m = re.match(r'^give\s+(\S+)\s+(\S+)(?:\s+(\d+))?\s*$', c, flags=re.IGNORECASE)
        if m:
            tgt = m.group(1)
            item = m.group(2)
            qty = m.group(3) or '1'
            if tgt.lower() in ('me', 'myself', 'self', '@p'):
                tgt = user
            if ':' not in item:
                item = f'minecraft:{item}'
            c = f'give {tgt} {item} {qty}'

        return c, None

    @staticmethod
    def _add_history(user: str, role: str, text: str):
        buf = OpAssistService._chat_history.setdefault(user.lower(), [])
        buf.append({'role': role, 'content': text})
        if len(buf) > 10:
            del buf[:-10]

    @staticmethod
    def _extract_command_from_text(user: str, content: str) -> Optional[str]:
        """Heuristic rescue parser when model JSON output is malformed."""
        t = (content or '').strip()
        if not t:
            return None

        # Strip fences and obvious chatter prefixes.
        t = re.sub(r'^```(?:json)?\s*', '', t, flags=re.IGNORECASE).strip()
        t = re.sub(r'\s*```$', '', t).strip()
        t = re.sub(r'^(ok|sure|done|i\'ll do that|running)[:\-\s]+', '', t, flags=re.IGNORECASE).strip()

        # If it already looks like a command, accept first line.
        first = t.splitlines()[0].strip() if t.splitlines() else t
        if first.startswith('/'):
            first = first[1:].strip()
        if re.match(r'^(give|time\s+set|weather|gamemode|tp|teleport|effect|summon|kill|say|clear|xp|experience|setworldspawn|spawnpoint|execute\s+in)\b', first, flags=re.IGNORECASE):
            return first

        # Try extracting command after keywords.
        m = re.search(r'(?:run|command)\s*[:\-]\s*(.+)$', t, flags=re.IGNORECASE)
        if m:
            cand = m.group(1).strip().splitlines()[0].strip()
            if cand.startswith('/'):
                cand = cand[1:].strip()
            if cand:
                return cand

        return None

    @staticmethod
    def _llm_call(user: str, text: str, can_execute: bool) -> dict:
        # Fallback if LLM disabled
        if not GEMMA_ENABLED:
            if can_execute:
                explicit = OpAssistService._extract_after_trigger(text)
                if explicit:
                    return {'type': 'command', 'command': explicit, 'say': f"running: {explicit}"}
            return {'type': 'chat', 'say': f"Hey {user}, I'm online as your guide. Ask me anything about Minecraft."}

        skill_md = OpAssistService._load_skill_markdown()
        exec_mode_line = (
            "- Execution mode: command execution is ENABLED for this player; use type=command for actionable requests.\n"
            if can_execute
            else "- Execution mode: command execution is DISABLED for this player/session; ALWAYS use type=chat and provide guidance only.\n"
        )
        system_prompt = (
            f"You are {AGENT_TRIGGER}, a Minecraft assistant and guide.\n"
            "Return STRICT JSON only with schema:\n"
            "{\"type\":\"chat\",\"say\":\"...\"} OR "
            "{\"type\":\"command\",\"command\":\"...\",\"say\":\"...\"}.\n"
            f"- The current player name is '{user}'. Use that exact name when targeting the player.\n"
            f"{exec_mode_line}"
            "- Never output host shell commands.\n"
            "- Never include placeholders.\n"
            "Reference command guide (follow strictly):\n"
            f"{skill_md}\n"
        )

        # conversation memory per user
        hist = OpAssistService._chat_history.get(user.lower(), [])
        messages = [{'role': 'system', 'content': system_prompt}] + hist + [{'role': 'user', 'content': text}]

        payload = {
            'model': GEMMA_OLLAMA_MODEL,
            'messages': messages,
            'temperature': GEMMA_TEMPERATURE,
            'stream': False,
            'options': {'num_ctx': GEMMA_CONTEXT_SIZE},
        }
        body = json.dumps(payload).encode('utf-8')

        req = urllib.request.Request(
            GEMMA_OLLAMA_URL,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'ARXDashboard/Gemma',
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            # Avoid vague drift after temporary API failures.
            if int(getattr(e, 'code', 0) or 0) >= 500:
                if can_execute:
                    explicit = OpAssistService._extract_after_trigger(text)
                    if explicit:
                        return {'type': 'command', 'command': explicit, 'say': f'running: {explicit}'}
                return {'type': 'chat', 'say': "Model backend is overloaded. Retry in a few seconds or lower context with: arx ai set-context 4096"}
            return {'type': 'chat', 'say': f"I hit API error ({e.code}). Try again."}
        except Exception:
            if can_execute:
                explicit = OpAssistService._extract_after_trigger(text)
                if explicit:
                    return {'type': 'command', 'command': explicit, 'say': f'running: {explicit}'}
            return {'type': 'chat', 'say': "Model backend connection issue. Retry in a moment."}

        # parse OpenAI-like response
        try:
            data = json.loads(raw)
            content = data['choices'][0]['message']['content']
        except Exception:
            return {'type': 'chat', 'say': "I couldn't parse the AI response. Try rephrasing."}

        # enforce JSON output parsing
        try:
            # strip code fences if any
            content = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.IGNORECASE)
            content = re.sub(r'\s*```$', '', content.strip())
            obj = json.loads(content)
            if not isinstance(obj, dict) or obj.get('type') not in ('chat', 'command'):
                raise ValueError('bad schema')
            return obj
        except Exception:
            # rescue path: if model output still contains a command-like line, only execute when permitted
            if can_execute:
                rescue = OpAssistService._extract_command_from_text(user, content)
                if rescue:
                    return {'type': 'command', 'command': rescue, 'say': f'running: {rescue}'}
            # fallback: treat as chat
            return {'type': 'chat', 'say': content[:GEMMA_MAX_REPLY_CHARS]}

    @staticmethod
    async def run_loop():
        state = load_op_assist_state()
        if LOG_FILE.exists() and state.get('log_offset', 0) <= 0:
            try:
                state['log_offset'] = LOG_FILE.stat().st_size
                save_op_assist_state(state)
            except Exception:
                pass

        while True:
            try:
                if not LOG_FILE.exists():
                    await asyncio.sleep(2)
                    continue

                size = LOG_FILE.stat().st_size
                offset = int(state.get('log_offset', 0) or 0)
                if offset < 0 or offset > size:
                    offset = max(0, size - 8192)

                if size > offset:
                    with LOG_FILE.open('rb') as f:
                        f.seek(offset)
                        raw = f.read(min(131072, size - offset))
                    chunk = raw.decode('utf-8', errors='replace')
                    state['log_offset'] = offset + len(raw)
                    save_op_assist_state(state)

                    ops = set(name.lower() for name in PlayerService.list_ops())
                    now = time.time()

                    for line in chunk.splitlines():
                        parsed = OpAssistService._parse_chat_line(line)
                        if not parsed:
                            continue
                        user, msg = parsed

                        is_op = user.lower() in ops
                        if not re.search(rf'\b{re.escape(AGENT_TRIGGER)}\b', msg, flags=re.IGNORECASE):
                            continue

                        # cooldown (all players)
                        last = OpAssistService._last_seen_by_user.get(user.lower(), 0.0)
                        if now - last < GEMMA_COOLDOWN_SEC:
                            continue
                        OpAssistService._last_seen_by_user[user.lower()] = now

                        OpAssistService._add_history(user, 'user', msg)
                        can_execute = OpAssistService._can_execute_commands_for_user(is_op=is_op)
                        decision = OpAssistService._llm_call(user, msg, can_execute)
                        decision = OpAssistService._enforce_permissions_on_decision(user, decision, can_execute)

                        if decision.get('type') == 'chat':
                            text = str(decision.get('say', f"Hey {user}."))
                            OpAssistService._add_history(user, 'assistant', text)
                            OpAssistService._say(text)
                            continue

                        # command path
                        cmd = str(decision.get('command', '')).strip()
                        if not cmd:
                            OpAssistService._say(f"{user}, I couldn't derive a valid command.")
                            continue

                        if cmd.startswith('/'):
                            cmd = cmd[1:].strip()

                        # normalize common player-target aliases/placeholders from AI output
                        cmd = re.sub(r'\b@p\b', user, cmd)
                        cmd = re.sub(r'\b(me|myself|self)\b', user, cmd, flags=re.IGNORECASE)
                        # Replace common LLM placeholders like <playername>, <player>, {player}
                        cmd = re.sub(r'(?i)<\s*player\s*name\s*>', user, cmd)
                        cmd = re.sub(r'(?i)<\s*player\s*>', user, cmd)
                        cmd = re.sub(r'(?i)\{\s*player\s*name\s*\}', user, cmd)
                        cmd = re.sub(r'(?i)\{\s*player\s*\}', user, cmd)
                        cmd = re.sub(r'(?i)\bplayername\b', user, cmd)
                        cmd = re.sub(r'(?i)\bplayer_name\b', user, cmd)

                        # normalize dimension wording typo from AI
                        cmd = cmd.replace('minecraft:nether', 'minecraft:the_nether')

                        # smart rewrite for natural teleport-to-dimension attempts
                        m_tp_dim = re.match(r'^tp\s+([A-Za-z0-9_@]+)\s+minecraft:(the_nether|the_end|overworld)\s*$', cmd, flags=re.IGNORECASE)
                        if m_tp_dim:
                            who = m_tp_dim.group(1)
                            dim = m_tp_dim.group(2).lower()
                            target = {
                                'the_nether': '0 80 0',
                                'the_end': '0 80 0',
                                'overworld': '0 80 0',
                            }[dim]
                            cmd = f'execute in minecraft:{dim} run tp {who} {target}'

                        # ensure gamemode commands target a player when omitted
                        m_gm = re.match(r'^gamemode\s+(survival|creative|adventure|spectator)\s*$', cmd, flags=re.IGNORECASE)
                        if m_gm:
                            mode = m_gm.group(1).lower()
                            cmd = f'gamemode {mode} {user}'

                        # refuse unresolved placeholders instead of pretending success
                        if re.search(r'<[^>]*>|\{[^}]*\}', cmd):
                            OpAssistService._say(f"{user}, I couldn't build a valid command yet. Please rephrase.")
                            continue

                        cmd, sanitize_err = OpAssistService._sanitize_command(user, cmd)
                        if sanitize_err:
                            OpAssistService._say(f"{user}, I blocked an unsafe command pattern. Please rephrase.")
                            continue
                        if not cmd:
                            OpAssistService._say(f"{user}, I couldn't derive a valid command.")
                            continue

                        if OpAssistService._is_blocked(cmd):
                            OpAssistService._say(f"sorry {user}, that command is blocked for safety.")
                            continue

                        res = ServerService.send_console_command(cmd, tier='admin', unsafe_ok=True)
                        if res.get('ok'):
                            say = str(decision.get('say', f"done {user} -> {cmd}"))
                            OpAssistService._add_history(user, 'assistant', say)
                            OpAssistService._say(say)
                        else:
                            detail = str(res.get('error', '')).strip()
                            if detail:
                                OpAssistService._say(f"sorry {user}, command failed: {detail[:120]}")
                            else:
                                OpAssistService._say(f"sorry {user}, command failed.")

            except Exception:
                pass

            await asyncio.sleep(2)
