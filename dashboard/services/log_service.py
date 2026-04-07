import re
import time

from ..config import LOG_FILE

CHAT_RE = re.compile(r"\]:\s*(?:\[[^\]]+\]\s*)?<([A-Za-z0-9_]{3,16})>\s*(.+)$")


class LogService:
    @staticmethod
    def diff_from(offset: int, max_bytes: int = 32768) -> dict:
        if not LOG_FILE.exists():
            return {'next_offset': 0, 'chunk': ''}
        size = LOG_FILE.stat().st_size
        if offset < 0 or offset > size:
            offset = max(0, size - max_bytes)
        to_read = min(max_bytes, max(0, size - offset))
        if to_read == 0:
            return {'next_offset': size, 'chunk': ''}
        with LOG_FILE.open('rb') as f:
            f.seek(offset)
            data = f.read(to_read)
        return {'next_offset': offset + to_read, 'chunk': data.decode('utf-8', errors='replace')}

    @staticmethod
    def extract_chat_events(chunk: str) -> list[dict]:
        events = []
        for line in chunk.splitlines():
            m = CHAT_RE.search(line)
            if not m:
                continue
            events.append({'user': m.group(1), 'message': m.group(2).strip(), 'raw': line})
        return events

    @staticmethod
    def wait_for_command_result(command: str, timeout_sec: float = 4.0) -> str:
        if not LOG_FILE.exists():
            return ''
        start = time.time()
        offset = LOG_FILE.stat().st_size
        needle = command.split()[0].lower() if command else ''
        while time.time() - start < timeout_sec:
            d = LogService.diff_from(offset, max_bytes=8192)
            offset = d['next_offset']
            chunk = d['chunk']
            if chunk and (needle in chunk.lower() or 'Unknown or incomplete command' in chunk or 'Error' in chunk):
                return chunk[-500:]
            time.sleep(0.25)
        return ''
