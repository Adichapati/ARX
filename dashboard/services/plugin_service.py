import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from ..config import PLUGINS_DIR, load_plugins_index, now_ts, save_plugins_index


class PluginService:
    # Curated and pinned download list.
    # Each item must define explicit source allowlist + expected sha256.
    CATALOG = [
        {
            'id': 'luckperms-bukkit',
            'name': 'LuckPerms (Bukkit)',
            'url': 'https://cdn.modrinth.com/data/Vebnzrzj/versions/OrIs0S6b/LuckPerms-Bukkit-5.5.17.jar',
            'kind': 'plugin',
            'sha256': 'd5b160a3971a8372cc5835bcd555e37c1aa61e9dd30559921a5f421a11bf97dd',
            'allowed_hosts': ['cdn.modrinth.com'],
        },
        {
            'id': 'vault',
            'name': 'Vault',
            'url': 'https://github.com/MilkBowl/Vault/releases/download/1.7.3/Vault.jar',
            'kind': 'plugin',
            'sha256': 'a6b5ed97f43a5cf5bbaf00a7c8cd23c5afc9bd003f849875af8b36e6cf77d01d',
            'allowed_hosts': ['github.com', 'release-assets.githubusercontent.com'],
        },
        {
            'id': 'fabric-api-modrinth',
            'name': 'Fabric API (Modrinth)',
            'url': 'https://cdn.modrinth.com/data/P7dR8mSH/versions/fm7UYECV/fabric-api-0.145.4%2B26.1.2.jar',
            'kind': 'mod',
            'sha256': 'f76f8a520ae752eddf2de4dd1704cdbd9e83711e0cb417f96e5b5e3a07fe7cbc',
            'allowed_hosts': ['cdn.modrinth.com'],
        },
    ]

    MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024

    @staticmethod
    def catalog() -> list[dict]:
        return PluginService.CATALOG

    @staticmethod
    def staged() -> list[dict]:
        return load_plugins_index()

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _host(url: str) -> str:
        try:
            return (urllib.parse.urlparse(url).hostname or '').lower().strip()
        except Exception:
            return ''

    @staticmethod
    def _is_allowed_host(url: str, allowed_hosts: list[str]) -> bool:
        host = PluginService._host(url)
        if not host:
            return False
        allowed = {str(h).strip().lower() for h in (allowed_hosts or []) if str(h).strip()}
        if not allowed:
            return False
        return host in allowed

    @staticmethod
    def stage_from_catalog(item_id: str) -> dict:
        found = next((x for x in PluginService.CATALOG if x['id'] == item_id), None)
        if not found:
            return {'ok': False, 'error': 'Unknown catalog item'}

        expected_sha = str(found.get('sha256', '')).strip().lower()
        if len(expected_sha) != 64 or any(c not in '0123456789abcdef' for c in expected_sha):
            return {'ok': False, 'error': 'Catalog entry missing valid pinned hash'}

        if not PluginService._is_allowed_host(str(found.get('url', '')), list(found.get('allowed_hosts', []))):
            return {'ok': False, 'error': 'Catalog entry source host is not allowlisted'}

        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        out_name = f"{item_id}-{int(now_ts())}.jar"
        out_path = PLUGINS_DIR / out_name

        req = urllib.request.Request(found['url'], headers={'User-Agent': 'ARXDashboard/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                final_url = r.geturl()
                if not PluginService._is_allowed_host(final_url, list(found.get('allowed_hosts', []))):
                    return {'ok': False, 'error': 'Download redirected to untrusted host'}

                data = r.read(PluginService.MAX_DOWNLOAD_BYTES + 1)
        except Exception as e:
            return {'ok': False, 'error': f'Download failed: {e}'}

        if not data:
            return {'ok': False, 'error': 'Downloaded file is empty'}
        if len(data) > PluginService.MAX_DOWNLOAD_BYTES:
            return {'ok': False, 'error': 'Downloaded file exceeds maximum allowed size'}

        out_path.write_bytes(data)
        sha = PluginService._sha256(out_path)
        if sha.lower() != expected_sha:
            try:
                os.remove(out_path)
            except Exception:
                pass
            return {'ok': False, 'error': 'Downloaded file hash mismatch'}

        size_mb = round(len(data) / (1024 * 1024), 2)

        idx = load_plugins_index()
        entry = {
            'id': item_id,
            'name': found['name'],
            'kind': found['kind'],
            'url': found['url'],
            'file': out_name,
            'sha256': sha,
            'size_mb': size_mb,
            'staged_at': int(now_ts()),
            'status': 'staged',
        }
        idx.insert(0, entry)
        save_plugins_index(idx[:80])

        return {'ok': True, 'message': f"Staged {found['name']}", 'entry': entry}

    @staticmethod
    def remove_staged(file_name: str) -> dict:
        if '/' in file_name or '..' in file_name:
            return {'ok': False, 'error': 'Invalid file name'}
        p = PLUGINS_DIR / file_name
        if p.exists():
            os.remove(p)

        idx = [x for x in load_plugins_index() if x.get('file') != file_name]
        save_plugins_index(idx)
        return {'ok': True, 'message': 'Removed staged file'}
