#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

need_cmd(){ command -v "$1" >/dev/null 2>&1 || return 1; }

echo "[ARX 1/8] Checking base dependencies..."
if ! need_cmd python3; then
  echo "python3 is required" >&2; exit 1
fi
if ! need_cmd java; then
  if need_cmd apt-get; then
    sudo apt-get update && sudo apt-get install -y openjdk-21-jre-headless
  else
    echo "Please install Java 21+ manually" >&2; exit 1
  fi
fi
if ! need_cmd tmux; then
  if need_cmd apt-get; then
    sudo apt-get update && sudo apt-get install -y tmux
  else
    echo "Please install tmux manually" >&2; exit 1
  fi
fi
if ! need_cmd curl; then
  if need_cmd apt-get; then
    sudo apt-get update && sudo apt-get install -y curl
  else
    echo "Please install curl manually" >&2; exit 1
  fi
fi

echo "[ARX 2/8] Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

echo "[ARX 3/8] Installing Python dependencies..."
pip install -r requirements.txt

echo "[ARX 4/8] Installing/checking Ollama..."
if ! need_cmd ollama; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
ollama serve >/tmp/arx-ollama.log 2>&1 &
sleep 2 || true
if ! ollama pull gemma4:e2b; then
  echo "ERROR: Failed to pull gemma4:e2b. Ensure Ollama is running and internet is available." >&2
  exit 1
fi

echo "[ARX 5/8] Preparing directories..."
mkdir -p app/minecraft_server/logs state scripts

echo "[ARX 6/8] Downloading latest vanilla server.jar..."
python3 - <<'PY'
import json, urllib.request, pathlib
root = pathlib.Path('.').resolve()
out = root / 'app' / 'minecraft_server' / 'server.jar'
manifest = json.load(urllib.request.urlopen('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json', timeout=20))
latest = manifest['latest']['release']
url = next(v['url'] for v in manifest['versions'] if v['id'] == latest)
ver = json.load(urllib.request.urlopen(url, timeout=20))
jar_url = ver['downloads']['server']['url']
with urllib.request.urlopen(jar_url, timeout=60) as r:
    out.write_bytes(r.read())
print(f'downloaded {latest} -> {out}')
PY

echo "[ARX 7/8] Creating secure .env if missing..."
if [ ! -f .env ]; then
  python3 - <<'PY'
import base64, hashlib, secrets, pathlib

def hash_pw(p: str) -> str:
    iters = 120000
    salt = secrets.token_bytes(16)
    out = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, iters)
    return f"pbkdf2_sha256${iters}${base64.b64encode(salt).decode()}${base64.b64encode(out).decode()}"

root = pathlib.Path('.').resolve()
pw = secrets.token_urlsafe(10)
session = secrets.token_urlsafe(32)
public = secrets.token_urlsafe(24)
content = f"""BIND_HOST=0.0.0.0
BIND_PORT=18890
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH={hash_pw(pw)}
SESSION_SECRET={session}
PUBLIC_READ_ENABLED=false
PUBLIC_READ_TOKEN={public}
MC_HOST=127.0.0.1
MC_PORT=25565
MC_TMUX_SESSION=mc_server_arx
GEMMA_ENABLED=true
GEMMA_OLLAMA_URL=http://localhost:11434/v1/chat/completions
GEMMA_OLLAMA_MODEL=gemma4:e2b
GEMMA_MAX_REPLY_CHARS=220
GEMMA_COOLDOWN_SEC=2.5
AGENT_TRIGGER=gemma
GEMMA_CONTEXT_SIZE=8192
GEMMA_TEMPERATURE=0.2
"""
(root / '.env').write_text(content, encoding='utf-8')
print('Generated .env')
print('Admin username: admin')
print(f'Temporary admin password: {pw}')
print('Change credentials after first login.')
PY
fi

echo "[ARX 8/8] Finalizing start scripts..."
chmod +x app/minecraft_server/start.sh scripts/start_dashboard.sh install.sh || true
echo "Installation complete."
echo "Run: ./scripts/start_dashboard.sh"
echo "Dashboard URL: http://localhost:18890/"
