#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

YES_MODE=false
FORCE_ENV=false
DASHBOARD_PORT=""
AGENT_TRIGGER=""
GEMMA_MODEL=""
GEMMA_CONTEXT_SIZE=""
GEMMA_TEMPERATURE=""
MC_VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) YES_MODE=true; shift ;;
    --force-env) FORCE_ENV=true; shift ;;
    --port) DASHBOARD_PORT="${2:-}"; shift 2 ;;
    --trigger) AGENT_TRIGGER="${2:-}"; shift 2 ;;
    --model) GEMMA_MODEL="${2:-}"; shift 2 ;;
    --context-size) GEMMA_CONTEXT_SIZE="${2:-}"; shift 2 ;;
    --temperature) GEMMA_TEMPERATURE="${2:-}"; shift 2 ;;
    --mc-version) MC_VERSION="${2:-}"; shift 2 ;;
    *)
      echo "Unknown flag: $1"
      echo "Usage: ./install.sh [--yes] [--force-env] [--port 18890] [--trigger gemma] [--model gemma4:e2b] [--context-size 8192] [--temperature 0.2] [--mc-version 1.20.4]"
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

UI_ENABLED=true
if [[ "$YES_MODE" == true ]] || [[ ! -t 1 ]]; then
  UI_ENABLED=false
fi

STEP_TOTAL=11
STEP_CUR=0

banner() {
  if [[ -n "${TERM:-}" && "$UI_ENABLED" == true ]]; then
    clear || true
  fi
  cat <<'EOF'

      ___      ____   __   __
     /   |    / __ \  \ \ / /
    / /| |   / /_/ /   \ V /
   / ___ |  / _, _/     > <
  /_/  |_| /_/ |_|     /_/\_\

+------------------------------------------------------------------+
| Agentic Runtime for eXecution | OpenClaw-style Setup            |
+------------------------------------------------------------------+
EOF
}

ascii_divider() {
  local tag="${1:-default}"
  case "$tag" in
    port)
      cat <<'EOF'
   +-----------+
   |  PORT CFG |
   +-----------+
EOF
      ;;
    trigger)
      cat <<'EOF'
   (o_o)  say the magic word
    \  gemma  /
     \______/
EOF
      ;;
    model)
      cat <<'EOF'
   [ GEMMA CORE ]
   > model select <
EOF
      ;;
    ctx)
      cat <<'EOF'
   [########      ]
   context tuning
EOF
      ;;
    temp)
      cat <<'EOF'
   ~ creativity dial ~
   low <----> high
EOF
      ;;
    admin)
      cat <<'EOF'
   +------------+
   |  ADMIN KEY |
   +------------+
EOF
      ;;
    *)
      cat <<'EOF'
   +-----------+
   |  ARX SET  |
   +-----------+
EOF
      ;;
  esac
}

prompt_with_art() {
  local title="$1"
  local tag="$2"
  local prompt="$3"
  if [[ "$UI_ENABLED" == true ]]; then
    banner
    box "$title"
  fi
  ascii_divider "$tag"
  read -rp "$prompt" REPLY
  printf '%s' "$REPLY"
}

select_from_list() {
  local title="$1"
  local tag="$2"
  local default_index="$3"
  shift 3
  local options=("$@")
  local index="$default_index"

  # Fallback mode (non-interactive): print list and ask numeric input
  if [[ "$UI_ENABLED" != true ]]; then
    banner
    box "$title"
    ascii_divider "$tag"
    local i
    for i in "${!options[@]}"; do
      printf '  [%d] %s\n' "$((i + 1))" "${options[$i]}"
    done
    while true; do
      read -rp "Choose 1-${#options[@]} (default $((default_index + 1))): " REPLY
      if [[ -z "$REPLY" ]]; then
        printf '%s' "${options[$default_index]}"
        return 0
      fi
      if [[ "$REPLY" =~ ^[0-9]+$ ]] && (( REPLY >= 1 && REPLY <= ${#options[@]} )); then
        printf '%s' "${options[$((REPLY - 1))]}"
        return 0
      fi
      echo "Invalid selection, try again."
    done
  fi

  while true; do
    banner
    box "$title"
    ascii_divider "$tag"
    echo "Use Up/Down arrows and Enter to choose."
    echo

    local i
    for i in "${!options[@]}"; do
      if (( i == index )); then
        printf '  > %s\n' "${options[$i]}"
      else
        printf '    %s\n' "${options[$i]}"
      fi
    done

    IFS= read -rsn1 key || true
    if [[ "$key" == "" ]]; then
      printf '%s' "${options[$index]}"
      return 0
    fi
    if [[ "$key" == $'\x1b' ]]; then
      IFS= read -rsn2 key2 || true
      case "$key2" in
        '[A')
          ((index--))
          if (( index < 0 )); then index=$((${#options[@]} - 1)); fi
          ;;
        '[B')
          ((index++))
          if (( index >= ${#options[@]} )); then index=0; fi
          ;;
      esac
    fi
  done
}

intro_animation() {
  if [[ "$UI_ENABLED" != true ]]; then
    return
  fi
  local i bar
  for i in 10 24 38 52 66 80 100; do
    bar=$(printf '%*s' $((i/2)) '' | tr ' ' '█')
    printf "\r[ARX] Initializing UI [% -50s] %3d%%" "$bar" "$i"
    sleep 0.08
  done
  printf "\n"
}

box() {
  local title="$1"
  echo
  echo "╔══════════════════════════════════════════════════════════════╗"
  printf "║ %-60s ║\n" "$title"
  echo "╚══════════════════════════════════════════════════════════════╝"
}

transition() {
  local text="$1"
  if [[ "$UI_ENABLED" == true ]]; then
    local dots=""
    for _ in 1 2 3; do
      dots+="."
      printf "\r[ARX] %s%s" "$text" "$dots"
      sleep 0.12
    done
    printf "\r%-72s\r" ""
  fi
  echo "[ARX] $text"
}

spinner_run() {
  local label="$1"
  shift

  local tmp pid frames i
  tmp="$(mktemp)"
  frames='|/-\\'

  "$@" >"$tmp" 2>&1 &
  pid=$!
  i=0

  if [[ "$UI_ENABLED" == true ]]; then
    while kill -0 "$pid" 2>/dev/null; do
      local c="${frames:i%4:1}"
      printf "\r  %s %s" "$c" "$label"
      i=$((i + 1))
      sleep 0.08
    done
  fi

  wait "$pid"
  local rc=$?

  if [[ "$UI_ENABLED" == true ]]; then
    printf "\r%-80s\r" ""
  fi

  if [[ $rc -eq 0 ]]; then
    if [[ "$UI_ENABLED" == true ]]; then
      printf "  ✓ %s\n" "$label"
    else
      echo "[ARX] $label: ok"
    fi
    rm -f "$tmp"
    return 0
  fi

  err "$label failed"
  sed -n '1,200p' "$tmp" >&2 || true
  rm -f "$tmp"
  return 1
}

tick_step() {
  STEP_CUR=$((STEP_CUR + 1))
  printf "[%02d/%02d] %s\n" "$STEP_CUR" "$STEP_TOTAL" "$1"
}

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
  if ! need_cmd python3; then err "python3 is required. Install Python 3.11+ and retry."; exit 1; fi

  if ! need_cmd java; then
    if [[ "$PLATFORM" == "linux" ]]; then
      install_pkg_linux openjdk-21-jre-headless || install_pkg_linux java-21-openjdk-headless || {
        err "Could not install Java automatically. Install Java 21+ manually."; exit 1;
      }
    elif [[ "$PLATFORM" == "macos" ]]; then
      need_cmd brew || { err "Homebrew required for auto-install on macOS. Install Java 21+ manually."; exit 1; }
      brew install openjdk@21
    else
      err "Unsupported OS for auto-install. Install Java 21+ manually."
      exit 1
    fi
  fi

  if ! need_cmd tmux; then
    if [[ "$PLATFORM" == "linux" ]]; then
      install_pkg_linux tmux || { err "Failed to install tmux."; exit 1; }
    elif [[ "$PLATFORM" == "macos" ]]; then
      need_cmd brew || { err "Homebrew required for auto-install on macOS. Install tmux manually."; exit 1; }
      brew install tmux
    else
      err "Unsupported OS for auto-install. Install tmux manually."
      exit 1
    fi
  fi

  if ! need_cmd curl; then
    if [[ "$PLATFORM" == "linux" ]]; then
      install_pkg_linux curl || { err "Failed to install curl."; exit 1; }
    elif [[ "$PLATFORM" == "macos" ]]; then
      need_cmd brew || { err "Homebrew required for auto-install on macOS. Install curl manually."; exit 1; }
      brew install curl
    else
      err "Unsupported OS for auto-install. Install curl manually."
      exit 1
    fi
  fi
}

ensure_ollama() {
  if ! need_cmd ollama; then
    if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "macos" ]]; then
      curl -fsSL https://ollama.com/install.sh | sh
    else
      err "Unsupported OS for automatic Ollama install in install.sh."
      err "Use Windows install.bat on Windows."
      exit 1
    fi
  fi

  if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
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
      _p="$(prompt_with_art "Dashboard Port" "port" "Dashboard port [18890]: ")"
      DASHBOARD_PORT="${_p:-18890}"
    fi
  fi

  if [[ -z "$AGENT_TRIGGER" ]]; then
    AGENT_TRIGGER="gemma"
    if [[ "$YES_MODE" == false ]]; then
      _t="$(prompt_with_art "Trigger Word" "trigger" "Agent trigger word [gemma]: ")"
      AGENT_TRIGGER="${_t:-gemma}"
    fi
  fi

  if [[ -z "$GEMMA_MODEL" ]]; then
    GEMMA_MODEL="gemma4:e2b"
    if [[ "$YES_MODE" == false ]]; then
      GEMMA_MODEL="$(select_from_list "Choose Gemma model" "model" 0 "gemma4:e2b" "gemma3:latest" "gemma2:9b")"
    fi
  fi

  if [[ -z "$GEMMA_CONTEXT_SIZE" ]]; then
    GEMMA_CONTEXT_SIZE="8192"
    if [[ "$YES_MODE" == false ]]; then
      GEMMA_CONTEXT_SIZE="$(select_from_list "Choose context size" "ctx" 1 "4096" "8192" "12288" "16384" "32768")"
    fi
  fi

  if [[ -z "$GEMMA_TEMPERATURE" ]]; then
    GEMMA_TEMPERATURE="0.2"
    if [[ "$YES_MODE" == false ]]; then
      GEMMA_TEMPERATURE="$(select_from_list "Choose temperature" "temp" 1 "0.1" "0.2" "0.3" "0.5" "0.7")"
    fi
  fi

  if [[ -z "$MC_VERSION" ]]; then
    MC_VERSION="1.20.4"
    if [[ "$YES_MODE" == false ]]; then
      _v="$(prompt_with_art "Minecraft Version" "default" "Minecraft version [1.20.4]: ")"
      MC_VERSION="${_v:-1.20.4}"
    fi
  fi

  ADMIN_USER="admin"
  ADMIN_PASS=""
  if [[ "$YES_MODE" == false ]]; then
    _u="$(prompt_with_art "Admin Account" "admin" "Admin username [admin]: ")"
    ADMIN_USER="${_u:-admin}"
    if [[ "$UI_ENABLED" == true ]]; then
      banner
      box "Admin Account"
      ascii_divider "admin"
    fi
    read -rsp "Admin password - leave blank to auto-generate: " _pw
    echo
    ADMIN_PASS="${_pw:-}"
  fi

  export ARX_ADMIN_USER="$ADMIN_USER"
  export ARX_ADMIN_PASS="$ADMIN_PASS"
}

validate_inputs() {
  if ! [[ "$DASHBOARD_PORT" =~ ^[0-9]+$ ]]; then err "Port must be numeric. Got: $DASHBOARD_PORT"; exit 1; fi
  if (( DASHBOARD_PORT < 1024 || DASHBOARD_PORT > 65535 )); then err "Port must be between 1024 and 65535. Got: $DASHBOARD_PORT"; exit 1; fi

  AGENT_TRIGGER="$(echo "$AGENT_TRIGGER" | tr '[:upper:]' '[:lower:]')"
  if ! [[ "$AGENT_TRIGGER" =~ ^[a-z0-9_-]{2,24}$ ]]; then err "Trigger must match [a-z0-9_-]{2,24}. Got: $AGENT_TRIGGER"; exit 1; fi

  if [[ -z "$GEMMA_MODEL" ]]; then err "Model cannot be empty."; exit 1; fi
  if [[ "$GEMMA_MODEL" != *:* ]]; then err "Model should look like 'name:tag' (e.g., gemma4:e2b). Got: $GEMMA_MODEL"; exit 1; fi

  if ! [[ "$ARX_ADMIN_USER" =~ ^[a-zA-Z0-9_.-]{3,32}$ ]]; then err "Admin username must match [a-zA-Z0-9_.-]{3,32}. Got: $ARX_ADMIN_USER"; exit 1; fi

  if ! [[ "$GEMMA_CONTEXT_SIZE" =~ ^[0-9]+$ ]]; then err "Context size must be numeric."; exit 1; fi
  if (( GEMMA_CONTEXT_SIZE < 1024 || GEMMA_CONTEXT_SIZE > 131072 )); then err "Context size must be 1024..131072."; exit 1; fi

  if ! [[ "$GEMMA_TEMPERATURE" =~ ^[0-9]+([.][0-9]+)?$ ]]; then err "Temperature must be numeric 0..2."; exit 1; fi
  awk -v t="$GEMMA_TEMPERATURE" 'BEGIN{exit (t>=0 && t<=2)?0:1}' || { err "Temperature must be 0..2"; exit 1; }

  if ! [[ "$MC_VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then err "Minecraft version must look like 1.20.4"; exit 1; fi
}

show_summary() {
  box "Setup Summary"
  echo "  Platform         : $PLATFORM"
  echo "  Dashboard port   : $DASHBOARD_PORT"
  echo "  Trigger          : $AGENT_TRIGGER"
  echo "  Gemma model      : $GEMMA_MODEL"
  echo "  Context size     : $GEMMA_CONTEXT_SIZE"
  echo "  Temperature      : $GEMMA_TEMPERATURE"
  echo "  Minecraft ver    : $MC_VERSION"
  echo "  Admin user       : $ARX_ADMIN_USER"
}

setup_python() {
  if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

setup_files() {
  mkdir -p app/minecraft_server/logs state scripts
}

download_server_jar() {
  if [[ -f app/minecraft_server/server.jar ]]; then
    return
  fi

  python3 - <<PY
import json, urllib.request, pathlib
root = pathlib.Path('.').resolve()
out = root / 'app' / 'minecraft_server' / 'server.jar'
manifest = json.load(urllib.request.urlopen('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json', timeout=20))
target = '${MC_VERSION}'
url = next((v['url'] for v in manifest['versions'] if v['id'] == target), None)
if not url:
    raise SystemExit(f'Could not resolve Minecraft version: {target}')
ver = json.load(urllib.request.urlopen(url, timeout=20))
jar_url = ver['downloads']['server']['url']
with urllib.request.urlopen(jar_url, timeout=60) as r:
    out.write_bytes(r.read())
print(f'downloaded {target} -> {out}')
PY
}

write_env() {
  if [[ -f .env && "$FORCE_ENV" == false ]]; then
    log ".env already exists (idempotent keep). Use --force-env to regenerate."
    return
  fi

  ARX_BIND_HOST="0.0.0.0" \
  ARX_BIND_PORT="$DASHBOARD_PORT" \
  ARX_ADMIN_USER="$ARX_ADMIN_USER" \
  ARX_ADMIN_PASS="$ARX_ADMIN_PASS" \
  ARX_TRIGGER="$AGENT_TRIGGER" \
  ARX_MODEL="$GEMMA_MODEL" \
  ARX_CONTEXT_SIZE="$GEMMA_CONTEXT_SIZE" \
  ARX_TEMPERATURE="$GEMMA_TEMPERATURE" \
  python3 scripts/generate_env.py --output .env
}

write_runtime_setup() {
  python3 - <<'PY'
import json
from pathlib import Path
import os
p = Path('state/arx_config.json')
p.parent.mkdir(parents=True, exist_ok=True)
obj = {
  'setup_completed': True,
  'agent_trigger': os.environ.get('AGENT_TRIGGER','gemma'),
  'gemma_model': os.environ.get('GEMMA_MODEL','gemma4:e2b'),
  'gemma_context_size': int(os.environ.get('GEMMA_CONTEXT_SIZE','8192')),
  'gemma_temperature': float(os.environ.get('GEMMA_TEMPERATURE','0.2')),
  'gemma_max_reply_chars': 220,
  'gemma_cooldown_sec': 2.5,
}
p.write_text(json.dumps(obj, indent=2), encoding='utf-8')
print('Wrote state/arx_config.json')
PY
}

finalize() {
  chmod +x app/minecraft_server/start.sh scripts/start_dashboard.sh install.sh scripts/generate_env.py || true
  box "Install Complete"
  echo "  Dashboard URL : http://localhost:${DASHBOARD_PORT}/"
  echo "  Start command : ./scripts/start_dashboard.sh"
  echo "  Gemma trigger : ${AGENT_TRIGGER}"
}

run_step() {
  local title="$1"
  shift
  tick_step "$title"
  if [[ "$UI_ENABLED" == true ]]; then
    spinner_run "$title" "$@"
  else
    "$@"
  fi
}

export DASHBOARD_PORT AGENT_TRIGGER GEMMA_MODEL GEMMA_CONTEXT_SIZE GEMMA_TEMPERATURE MC_VERSION

banner
intro_animation
transition "Opening setup"
box "Interactive First-Run"
prompt_if_needed
validate_inputs
show_summary

transition "Running installation pipeline"
run_step "Prerequisite checks" install_prereqs
run_step "Python environment" setup_python
run_step "Ollama + model readiness" ensure_ollama
run_step "Project directories" setup_files
run_step "Minecraft server jar" download_server_jar
run_step "Secure env generation" write_env
run_step "Runtime setup profile" write_runtime_setup
run_step "Finalize installer" finalize

if [[ "$UI_ENABLED" == true ]]; then
  transition "All done"
fi
