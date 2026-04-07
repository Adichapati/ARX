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
    parser.add_argument('--admin-user', default='admin')
    parser.add_argument('--admin-pass', default='')
    parser.add_argument('--trigger', default='gemma')
    parser.add_argument('--model', default='gemma4:e2b')
    args = parser.parse_args()

    admin_pass = args.admin_pass or secrets.token_urlsafe(10)

    content = f"""BIND_HOST={args.bind_host}
BIND_PORT={args.bind_port}
AUTH_USERNAME={args.admin_user}
AUTH_PASSWORD_HASH={hash_pw(admin_pass)}
SESSION_SECRET={secrets.token_urlsafe(32)}
PUBLIC_READ_ENABLED=false
PUBLIC_READ_TOKEN={secrets.token_urlsafe(24)}
MC_HOST=127.0.0.1
MC_PORT=25565
MC_TMUX_SESSION=mc_server_arx
GEMMA_ENABLED=true
GEMMA_OLLAMA_URL=http://localhost:11434/v1/chat/completions
GEMMA_OLLAMA_MODEL={args.model}
GEMMA_MAX_REPLY_CHARS=220
GEMMA_COOLDOWN_SEC=2.5
AGENT_TRIGGER={args.trigger}
GEMMA_CONTEXT_SIZE=8192
GEMMA_TEMPERATURE=0.2
"""

    out = Path(args.output)
    out.write_text(content, encoding='utf-8')

    print('Generated .env')
    print(f'Admin username: {args.admin_user}')
    print(f'Temporary admin password: {admin_pass}')
    print('Change credentials after first login.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
