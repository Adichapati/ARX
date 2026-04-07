from ..config import EULA_PATH, SERVER_PROPERTIES_PATH


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
