from collections import deque

from ..config import LOG_FILE, _player_hist, now_ts


class LogService:
    @staticmethod
    def tail(lines: int = 120) -> str:
        if not LOG_FILE.exists():
            return 'No logs yet.'

        try:
            if lines <= 0:
                return ''

            with LOG_FILE.open('r', encoding='utf-8', errors='replace') as f:
                tail_lines = deque((line.rstrip('\r\n') for line in f), maxlen=lines)
            return '\n'.join(tail_lines)
        except Exception:
            return 'Failed to read logs'

    @staticmethod
    def diff_from(offset: int, max_bytes: int = 32_768) -> dict:
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

        text = data.decode('utf-8', errors='replace')
        return {'next_offset': offset + to_read, 'chunk': text}


class AnalyticsService:
    @staticmethod
    def summary(hours: int = 6) -> dict:
        cutoff = now_ts() - hours * 3600
        samples = [x for x in _player_hist if x['t'] >= cutoff]
        if not samples:
            return {'window_hours': hours, 'avg_players': 0, 'peak_players': 0, 'uptime_percent': 0}

        avg_players = sum(x['players'] for x in samples) / len(samples)
        peak_players = max(x['players'] for x in samples)
        up_pct = sum(1 for x in samples if x['running']) / len(samples) * 100
        return {
            'window_hours': hours,
            'avg_players': round(avg_players, 2),
            'peak_players': int(peak_players),
            'uptime_percent': round(up_pct, 1),
            'samples': len(samples),
        }
