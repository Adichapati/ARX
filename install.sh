#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

YES_MODE=false
FORCE_ENV=false
DASHBOARD_PORT=""
AGENT_TRIGGER=""
GEMMA_MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y)
      YES_MODE=true
      shift
      ;;
    --force-env)
      FORCE_ENV=true
      shift
      ;;
    --port)
      DASHBOARD_PORT="${2:-}"
      shift 2
      ;;
    --trigger)
      AGENT_TRIGGER="${2:-}"
      shift 2
      ;;
    --model)
      GEMMA_MODEL="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown flag: $1"
      echo "Usage: ./install.sh [--yes] [--force-env] [--port 18890] [--trigger gemma] [--model gemma4:e2b]"
      exit 1
      ;;
  esac
done

need_cmd() { command -v "$1" >/dev/null 2>&1; }
log() { echo "[ARX] $*"; }
err() { echo "[ARX][ERROR] $*" >&2; }

OS="$(uname -s)"
case "$OS" in
  Linux*) PLATFORM="linux" ;;
  Darwin*) PLATFORM="macos" ;;
  *) PLATFORM="unknown" ;;
esac

install_pkg_linux() {
  local pkg="$1"
  if need_cmd apt-get; then
    sudo apt-get update -y
    sudo apt-get install -y "$pkg"
  elif need_cmd dnf; then
    sudo dnf install -y "$pkg"
  elif need_cmd yum; then
    sudo yum install -y "$pkg"
  elif need_cmd pacman; then
    sudo pacman -Sy --noconfirm "$pkg"
  else
    err "No supported Linux package manager found for installing '$pkg'."
    return 1
  fi
}

install_prereqs() {
  log "Checking base dependencies..."

  if ! need_cmd python3; then
    err "python3 is required. Install Python 3.11+ and retry."
    exit 1
  fi

  if ! need_cmd java; then
    log "Installing Java runtime..."
    if [[ "$PLATFORM" == "linux" ]]; then
      install_pkg_linux openjdk-21-jre-headless || install_pkg_linux java-21-openjdk-headless || {
        err "Could not install Java automatically. Install Java 21+ manually."; exit 1;
      }
    elif [[ "$PLATFORM" == "macos" ]]; then
      if need_cmd brew; then
        brew install openjdk@21
      else
        err "Homebrew required for auto-install on macOS. Install Java 21+ manually."
        exit 1
      fi
    else
      err "Unsupported OS for auto-install. Install Java 21+ manually."
      exit 1
    fi
  fi

  if ! need_cmd tmux; then
    log "Installing tmux..."
    if [[ "$PLATFORM" == "linux" ]]; then
      install_pkg_linux tmux || { err "Failed to install tmux."; exit 1; }
    elif [[ "$PLATFORM" == "macos" ]]; then
      if need_cmd brew; then
        brew install tmux
      else
        err "Homebrew required for auto-install on macOS. Install tmux manually."
        exit 1
      fi
    else
      err "Unsupported OS for auto-install. Install tmux manually."
      exit 1
    fi
  fi

  if ! need_cmd curl; then
    log "Installing curl..."
    if [[ "$PLATFORM" == "linux" ]]; then
      install_pkg_linux curl || { err "Failed to install curl."; exit 1; }
    elif [[ "$PLATFORM" == "macos" ]]; then
      if need_cmd brew; then
        brew install curl
      else
        err "Homebrew required for auto-install on macOS. Install curl manually."
        exit 1
      fi
    else
      err "Unsupported OS for auto-install. Install curl manually."
      exit 1
    fi
  fi
}

ensure_ollama() {
  log "Checking Ollama..."

  if ! need_cmd ollama; then
    log "Ollama not found. Installing for $PLATFORM..."
    if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "macos" ]]; then
      curl -fsSL https://ollama.com/install.sh | sh
    else
      err "Unsupported OS for automatic Ollama install in install.sh."
      err "Use Windows install.bat on Windows."
      exit 1
    fi
  fi

  if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    log "Starting local Ollama service..."
    nohup ollama serve >/tmp/arx-ollama.log 2>&1 &
  fi

  local tries=0
  until curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [[ $tries -ge 20 ]]; then
      err "Ollama API is not reachable at http://127.0.0.1:11434"
      err "Start Ollama manually and rerun installer."
      exit 1
    fi
    sleep 1
  done

  log "Ensuring model '${GEMMA_MODEL}' is available..."
  if ! ollama pull "$GEMMA_MODEL"; then
    err "Failed to pull model '$GEMMA_MODEL'."
    err "Check internet connection and Ollama service status."
    exit 1
  fi
}

prompt_if_needed() {
  if [[ -z "$DASHBOARD_PORT" ]]; then
    DASHBOARD_PORT="18890"
    if [[ "$YES_MODE" == false ]]; then
      read -rp "Dashboard port [18890]: " _p
      DASHBOARD_PORT="${_p:-18890}"
    fi
  fi

  if [[ -z "$AGENT_TRIGGER" ]]; then
    AGENT_TRIGGER="gemma"
    if [[ "$YES_MODE" == false ]]; then
      read -rp "Agent trigger word [gemma]: " _t
      AGENT_TRIGGER="${_t:-gemma}"
    fi
  fi

  if [[ -z "$GEMMA_MODEL" ]]; then
    GEMMA_MODEL="gemma4:e2b"
    if [[ "$YES_MODE" == false ]]; then
      read -rp "Gemma model [gemma4:e2b]: " _m
      GEMMA_MODEL="${_m:-gemma4:e2b}"
    fi
  fi

  ADMIN_USER="admin"
  ADMIN_PASS=""
  if [[ "$YES_MODE" == false ]]; then
    read -rp "Admin username [admin]: " _u
    ADMIN_USER="${_u:-admin}"
    read -rsp "Admin password (leave blank to auto-generate): " _pw
    echo
    ADMIN_PASS="${_pw:-}"
  fi

  export ARX_ADMIN_USER="$ADMIN_USER"
  export ARX_ADMIN_PASS="$ADMIN_PASS"
}

validate_inputs() {
  if ! [[ "$DASHBOARD_PORT" =~ ^[0-9]+$ ]]; then
    err "Port must be numeric. Got: $DASHBOARD_PORT"
    exit 1
  fi
  if (( DASHBOARD_PORT < 1024 || DASHBOARD_PORT > 65535 )); then
    err "Port must be between 1024 and 65535. Got: $DASHBOARD_PORT"
    exit 1
  fi

  AGENT_TRIGGER="$(echo "$AGENT_TRIGGER" | tr '[:upper:]' '[:lower:]')"
  if ! [[ "$AGENT_TRIGGER" =~ ^[a-z0-9_-]{2,24}$ ]]; then
    err "Trigger must match [a-z0-9_-]{2,24}. Got: $AGENT_TRIGGER"
    exit 1
  fi

  if [[ -z "$GEMMA_MODEL" ]]; then
    err "Model cannot be empty."
    exit 1
  fi
  if [[ "$GEMMA_MODEL" != *:* ]]; then
    err "Model should look like 'name:tag' (e.g., gemma4:e2b). Got: $GEMMA_MODEL"
    exit 1
  fi

  if ! [[ "$ARX_ADMIN_USER" =~ ^[a-zA-Z0-9_.-]{3,32}$ ]]; then
    err "Admin username must match [a-zA-Z0-9_.-]{3,32}. Got: $ARX_ADMIN_USER"
    exit 1
  fi
}

setup_python() {
  log "Setting up Python environment..."
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

setup_files() {
  log "Preparing directories..."
  mkdir -p app/minecraft_server/logs state scripts
}

download_server_jar() {
  if [[ -f app/minecraft_server/server.jar ]]; then
    log "server.jar already exists (idempotent skip)."
    return
  fi

  log "Downloading latest vanilla server.jar..."
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
}

write_env() {
  if [[ -f .env && "$FORCE_ENV" == false ]]; then
    log ".env already exists (idempotent keep). Use --force-env to regenerate."
    return
  fi

  log "Generating secure .env..."
  python3 - <<'PY'
import base64, hashlib, secrets, pathlib, os

def hash_pw(p: str) -> str:
    iters = 120000
    salt = secrets.token_bytes(16)
    out = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, iters)
    return f"pbkdf2_sha256${iters}${base64.b64encode(salt).decode()}${base64.b64encode(out).decode()}"

root = pathlib.Path('.').resolve()
admin_user = os.environ.get('ARX_ADMIN_USER', 'admin')
admin_pass = os.environ.get('ARX_ADMIN_PASS', '') or secrets.token_urlsafe(10)
session = secrets.token_urlsafe(32)
public = secrets.token_urlsafe(24)
port = os.environ.get('DASHBOARD_PORT', '18890')
trigger = os.environ.get('AGENT_TRIGGER', 'gemma')
model = os.environ.get('GEMMA_MODEL', 'gemma4:e2b')

content = f"""BIND_HOST=0.0.0.0
BIND_PORT={port}
AUTH_USERNAME={admin_user}
AUTH_PASSWORD_HASH={hash_pw(admin_pass)}
SESSION_SECRET={session}
PUBLIC_READ_ENABLED=false
PUBLIC_READ_TOKEN={public}
MC_HOST=127.0.0.1
MC_PORT=25565
MC_TMUX_SESSION=mc_server_arx
GEMMA_ENABLED=true
GEMMA_OLLAMA_URL=http://localhost:11434/v1/chat/completions
GEMMA_OLLAMA_MODEL={model}
GEMMA_MAX_REPLY_CHARS=220
GEMMA_COOLDOWN_SEC=2.5
AGENT_TRIGGER={trigger}
GEMMA_CONTEXT_SIZE=8192
GEMMA_TEMPERATURE=0.2
"""
(root / '.env').write_text(content, encoding='utf-8')
print('Generated .env')
print(f'Admin username: {admin_user}')
print(f'Temporary admin password: {admin_pass}')
print('Change credentials after first login.')
PY
}

finalize() {
  chmod +x app/minecraft_server/start.sh scripts/start_dashboard.sh install.sh || true
  log "Installation complete."
  log "Run: ./scripts/start_dashboard.sh"
  log "Dashboard URL: http://localhost:${DASHBOARD_PORT}/"
}

export DASHBOARD_PORT AGENT_TRIGGER GEMMA_MODEL

prompt_if_needed
validate_inputs
install_prereqs
setup_python
ensure_ollama
setup_files
download_server_jar
write_env
finalize
