import json

from ..config import EULA_PATH, ROOT, SERVER_PROPERTIES_PATH

ARX_CONFIG_PATH = ROOT / 'state' / 'arx_config.json'


class ConfigService:
    @staticmethod
    def ensure_eula() -> None:
        if not EULA_PATH.exists() or 'eula=true' not in EULA_PATH.read_text(encoding='utf-8', errors='ignore'):
            EULA_PATH.write_text('eula=true\n', encoding='utf-8')

    @staticmethod
    def read_server_properties() -> dict:
        if not SERVER_PROPERTIES_PATH.exists():
            return {}
        out = {}
        for line in SERVER_PROPERTIES_PATH.read_text(encoding='utf-8', errors='ignore').splitlines():
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip()
        return out

    @staticmethod
    def load_arx_runtime_config() -> dict:
        defaults = {
            'setup_completed': False,
            'agent_trigger': 'gemma',
            'gemma_model': 'gemma4:e2b',
            'gemma_context_size': 8192,
            'gemma_temperature': 0.2,
            'gemma_max_reply_chars': 220,
            'gemma_cooldown_sec': 2.5,
        }
        if not ARX_CONFIG_PATH.exists():
            return defaults
        try:
            data = json.loads(ARX_CONFIG_PATH.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass
        return defaults

    @staticmethod
    def save_arx_runtime_config(cfg: dict) -> dict:
        current = ConfigService.load_arx_runtime_config()
        current.update(cfg or {})
        ARX_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARX_CONFIG_PATH.write_text(json.dumps(current, indent=2), encoding='utf-8')
        return current

    @staticmethod
    def validate_runtime_updates(updates: dict) -> dict:
        clean = {}

        if 'agent_trigger' in updates:
            t = str(updates['agent_trigger']).strip().lower()
            if not (2 <= len(t) <= 24) or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in t):
                raise ValueError('agent_trigger must be 2-24 chars [a-z0-9_-]')
            clean['agent_trigger'] = t

        if 'gemma_model' in updates:
            m = str(updates['gemma_model']).strip()
            if ':' not in m or len(m) < 3:
                raise ValueError('gemma_model must look like name:tag (e.g., gemma4:e2b)')
            clean['gemma_model'] = m

        if 'gemma_context_size' in updates:
            c = int(updates['gemma_context_size'])
            if c < 1024 or c > 131072:
                raise ValueError('gemma_context_size must be 1024..131072')
            clean['gemma_context_size'] = c

        if 'gemma_temperature' in updates:
            t = float(updates['gemma_temperature'])
            if t < 0 or t > 2:
                raise ValueError('gemma_temperature must be 0..2')
            clean['gemma_temperature'] = round(t, 3)

        if 'gemma_max_reply_chars' in updates:
            m = int(updates['gemma_max_reply_chars'])
            if m < 80 or m > 500:
                raise ValueError('gemma_max_reply_chars must be 80..500')
            clean['gemma_max_reply_chars'] = m

        if 'gemma_cooldown_sec' in updates:
            cd = float(updates['gemma_cooldown_sec'])
            if cd < 0 or cd > 30:
                raise ValueError('gemma_cooldown_sec must be 0..30')
            clean['gemma_cooldown_sec'] = round(cd, 2)

        if 'setup_completed' in updates:
            clean['setup_completed'] = bool(updates['setup_completed'])

        return clean
