import socket
import urllib.error
import urllib.request

import psutil

from ..config import (
    BIND_HOST,
    BIND_PORT,
    MC_PORT,
    PLAYIT_URL,
    PUBLIC_READ_ENABLED,
    PUBLIC_READ_TOKEN,
    _cache,
    _metrics_hist,
    _player_hist,
    _public_ip_cache,
    _scheduler,
    now_ts,
    state,
)
from .server_service import ServerService


def public_ip_cached() -> str:
    now = now_ts()
    if _public_ip_cache['expires_at'] > now:
        return _public_ip_cache['value']

    try:
        req = urllib.request.Request(
            'https://api.ipify.org',
            headers={'User-Agent': 'ARX/1.0 snapshot-service'},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            ip = resp.read().decode('utf-8', errors='ignore').strip()
        if ip:
            _public_ip_cache['value'] = ip
            _public_ip_cache['expires_at'] = now + 600
            return ip
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        pass

    _public_ip_cache['expires_at'] = now + 120
    return _public_ip_cache['value']


def _local_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            if ip:
                return ip
        finally:
            s.close()
    except Exception:
        pass
    return '127.0.0.1'


def build_snapshot() -> dict:
    vm = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=None)
    mq = ServerService.mc_query()
    ip = public_ip_cached()
    lan_ip = _local_lan_ip()

    _metrics_hist.append({'cpu': round(cpu, 1), 'ram': round(vm.percent, 1), 't': now_ts()})
    _player_hist.append({'players': mq['players_online'], 'running': 1 if ServerService.is_running() else 0, 't': now_ts()})

    return {
        'running': ServerService.is_running(),
        'server_info': {
            'host': f'127.0.0.1:{MC_PORT}',
            'lan': f'{lan_ip}:{MC_PORT}',
            'public': f'{ip}:{MC_PORT}',
            'connect_address': (PLAYIT_URL.strip() if PLAYIT_URL.strip() else f'{lan_ip}:{MC_PORT}'),
            'connect_mode': ('playit' if PLAYIT_URL.strip() else 'lan'),
            'version': mq['version'],
            'players': f"{mq['players_online']}/{mq['players_max']}",
            'players_online': mq['players_online'],
            'players_max': mq['players_max'],
            'player_names': mq.get('player_names', []),
            'latency_ms': mq['latency_ms'],
        },
        'dashboard': {
            'bind': f'{BIND_HOST}:{BIND_PORT}',
            'private_link': f'http://{ip}:{BIND_PORT}/',
            'public_readonly_link': (
                f'http://{ip}:{BIND_PORT}/public/{PUBLIC_READ_TOKEN}' if PUBLIC_READ_ENABLED else ''
            ),
            'public_read_enabled': bool(PUBLIC_READ_ENABLED),
        },
        'metrics': {
            'cpu_percent': round(cpu, 1),
            'memory_percent': round(vm.percent, 1),
            'memory_used_gb': round((vm.total - vm.available) / (1024 ** 3), 2),
            'memory_total_gb': round(vm.total / (1024 ** 3), 2),
        },
        'automation': {
            'auto_start': state['auto_start'],
            'auto_stop': state['auto_stop'],
            'last_status_note': state['last_status_note'],
            'last_action': state['last_action'],
            'restart_minutes': _scheduler.get('restart_minutes', 0),
            'backup_minutes': _scheduler.get('backup_minutes', 0),
        },
    }


def get_snapshot() -> dict:
    if _cache['snapshot'] is None:
        _cache['snapshot'] = build_snapshot()
        _cache['updated_at'] = now_ts()
    return _cache['snapshot']
