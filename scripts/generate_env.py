#!/usr/bin/env python3
import argparse
import base64
import hashlib
import secrets
from pathlib import Path


def hash_pw(password: str) -> str:
    iterations = 120000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate ARX .env file')
    parser.add_argument('--output', default='.env')
    parser.add_argument('--bind-host', default='0.0.0.0')
    parser.add_argument('--bind-port', default='18890')
    parser.add_argument('--admin-user', default='')
    parser.add_argument('--admin-pass', default='')
    parser.add_argument('--trigger', default='gemma')
    parser.add_argument('--model', default='gemma4:e2b')
    parser.add_argument('--ollama-url', default='http://localhost:11434/v1/chat/completions')
    parser.add_argument('--playit-enabled', default='false')
    parser.add_argument('--playit-url', default='')
    args = parser.parse_args()

    import os
    bind_host = args.bind_host or os.environ.get('ARX_BIND_HOST', '0.0.0.0')
    bind_port = args.bind_port or os.environ.get('ARX_BIND_PORT', '18890')
    admin_user = args.admin_user or os.environ.get('ARX_ADMIN_USER', 'admin')
    admin_pass = args.admin_pass or os.environ.get('ARX_ADMIN_PASS', '') or secrets.token_urlsafe(10)
    trigger = args.trigger or os.environ.get('ARX_TRIGGER', 'gemma')
    model = args.model or os.environ.get('ARX_MODEL', 'gemma4:e2b')
    ollama_url = args.ollama_url or os.environ.get('ARX_OLLAMA_URL', 'http://localhost:11434/v1/chat/completions')
    playit_enabled = (args.playit_enabled or os.environ.get('ARX_PLAYIT_ENABLED', 'false')).strip().lower()
    playit_url = args.playit_url or os.environ.get('ARX_PLAYIT_URL', '')
    context_size = os.environ.get('ARX_CONTEXT_SIZE', '8192')
    temperature = os.environ.get('ARX_TEMPERATURE', '0.2')

    content = f"""BIND_HOST={bind_host}
BIND_PORT={bind_port}
AUTH_USERNAME={admin_user}
AUTH_PASSWORD_HASH={hash_pw(admin_pass)}
SESSION_SECRET={secrets.token_urlsafe(32)}
PUBLIC_READ_ENABLED=false
PUBLIC_READ_TOKEN={secrets.token_urlsafe(24)}
MC_HOST=127.0.0.1
MC_PORT=25565
MC_TMUX_SESSION=mc_server_arx
GEMMA_ENABLED=true
GEMMA_OLLAMA_URL={ollama_url}
GEMMA_OLLAMA_MODEL={model}
GEMMA_MAX_REPLY_CHARS=220
GEMMA_COOLDOWN_SEC=2.5
AGENT_TRIGGER={trigger}
GEMMA_CONTEXT_SIZE={context_size}
GEMMA_TEMPERATURE={temperature}
PLAYIT_ENABLED={playit_enabled}
PLAYIT_URL={playit_url}
"""

    out = Path(args.output)
    out.write_text(content, encoding='utf-8')

    print('Generated .env')
    print(f'Admin username: {admin_user}')
    print(f'Temporary admin password: {admin_pass}')
    print('Change credentials after first login.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
