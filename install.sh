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
PLAYIT_ENABLED=""
PLAYIT_URL=""
ADMIN_USER=""
ADMIN_PASS=""

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
    --playit-enabled) PLAYIT_ENABLED="${2:-}"; shift 2 ;;
    --playit-url) PLAYIT_URL="${2:-}"; shift 2 ;;
    --admin-user) ADMIN_USER="${2:-}"; shift 2 ;;
    --admin-pass) ADMIN_PASS="${2:-}"; shift 2 ;;
    *)
      echo "Unknown flag: $1"
      echo "Usage: ./install.sh [--yes] [--force-env] [--port 18890] [--trigger gemma] [--model gemma4:e2b] [--context-size 4096] [--temperature 0.2] [--mc-version 1.20.4] [--playit-enabled true|false] [--playit-url <public-tunnel>] [--admin-user admin] [--admin-pass <password>]"
      exit 1
      ;;
  esac
done

need_cmd() { command -v "$1" >/dev/null 2>&1; }
log() { echo "[ARX] $*"; }
err() { echo "[ARX][ERROR] $*" >&2; }

SUDO_READY=false
SUDO_KEEPALIVE_PID=""

ensure_sudo_ready() {
  local allow_prompt="${1:-false}"

  if [[ "$EUID" -eq 0 ]]; then
    SUDO_READY=true
    return 0
  fi

  if ! need_cmd sudo; then
    err "This step requires administrator privileges, but 'sudo' is not available."
    err "Install sudo or run installer as root."
    return 1
  fi

  if sudo -n true >/dev/null 2>&1; then
    SUDO_READY=true
    return 0
  fi

  if [[ "$allow_prompt" == "true" && -t 0 && -t 1 ]]; then
    log "Administrator privileges are required for dependency installation."
    log "Please enter your sudo password once to continue."
    if sudo -v; then
      if sudo -n true >/dev/null 2>&1; then
        # Keep sudo ticket fresh during long installs to avoid mid-step prompts.
        ( while true; do sudo -n true >/dev/null 2>&1 || exit 0; sleep 45; done ) &
        SUDO_KEEPALIVE_PID=$!
        trap '[[ -n "${SUDO_KEEPALIVE_PID:-}" ]] && kill "$SUDO_KEEPALIVE_PID" >/dev/null 2>&1 || true' EXIT

        SUDO_READY=true
        return 0
      fi
    fi
  fi

  err "Administrator privileges are required, but sudo credentials are not available."
  err "Run 'sudo -v' in this terminal, then rerun ./install.sh"
  return 1
}

run_as_root() {
  if [[ "$EUID" -eq 0 ]]; then
    "$@"
    return $?
  fi

  ensure_sudo_ready false || return 1
  sudo -n "$@"
}

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
| Agentic Runtime for eXecution | Production Setup                |
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
    run_as_root env DEBIAN_FRONTEND=noninteractive apt-get -o Dpkg::Lock::Timeout=120 update -y
    run_as_root env DEBIAN_FRONTEND=noninteractive apt-get -o Dpkg::Lock::Timeout=120 install -y --no-install-recommends "$pkg"
  elif need_cmd dnf; then
    run_as_root dnf install -y "$pkg"
  elif need_cmd yum; then
    run_as_root yum install -y "$pkg"
  elif need_cmd pacman; then
    run_as_root pacman -Sy --noconfirm "$pkg"
  else
    err "No supported Linux package manager found for installing '$pkg'."
    return 1
  fi
}

preflight_privileges() {
  if [[ "$PLATFORM" != "linux" ]]; then
    return
  fi

  local needs_priv=false

  if [[ "$(java_major)" -lt 21 ]]; then
    needs_priv=true
  fi

  if ! need_cmd tmux; then
    needs_priv=true
  fi

  if ! need_cmd curl; then
    needs_priv=true
  fi

  if ! need_cmd ollama; then
    needs_priv=true
  fi

  if [[ "$needs_priv" == true ]]; then
    ensure_sudo_ready true || exit 1
  fi
}

java_major() {
  if ! need_cmd java; then
    echo 0
    return 0
  fi
  local line
  line="$(java -version 2>&1 | head -n1 || true)"
  if [[ "$line" =~ version\ "1\.([0-9]+) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi
  if [[ "$line" =~ version\ "([0-9]+) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi
  echo 0
}

ensure_java_runtime() {
  local min_major=21
  local current
  current="$(java_major)"
  if [[ "$current" -ge "$min_major" ]]; then
    log "Java runtime detected (major=$current)."
    return 0
  fi

  log "Java ${min_major}+ required. Attempting automatic install/upgrade..."
  if [[ "$PLATFORM" == "linux" ]]; then
    local pkgs=(
      openjdk-25-jre-headless java-25-openjdk-headless
      openjdk-24-jre-headless java-24-openjdk-headless
      openjdk-23-jre-headless java-23-openjdk-headless
      openjdk-22-jre-headless java-22-openjdk-headless
      openjdk-21-jre-headless java-21-openjdk-headless
    )
    local ok=false
    local p
    for p in "${pkgs[@]}"; do
      if install_pkg_linux "$p"; then
        ok=true
        break
      fi
    done
    if [[ "$ok" != true ]]; then
      err "Could not install Java automatically. Install Java 21+ manually and rerun installer."
      return 1
    fi
  elif [[ "$PLATFORM" == "macos" ]]; then
    need_cmd brew || { err "Homebrew required for auto-install on macOS. Install Java 21+ manually."; return 1; }
    brew install openjdk || brew install openjdk@21 || {
      err "Could not install Java automatically on macOS. Install Java 21+ manually."
      return 1
    }
  else
    err "Unsupported OS for auto-install. Install Java 21+ manually."
    return 1
  fi

  current="$(java_major)"
  if [[ "$current" -lt "$min_major" ]]; then
    err "Java install/upgrade completed but runtime is still below Java ${min_major}."
    err "Install Java 21+ manually and retry."
    return 1
  fi
  log "Java runtime ready (major=$current)."
}

install_prereqs() {
  if ! need_cmd python3; then err "python3 is required. Install Python 3.11+ and retry."; exit 1; fi

  ensure_java_runtime || exit 1

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
      local tmp_installer
      tmp_installer="$(mktemp)"
      curl -fsSL https://ollama.com/install.sh -o "$tmp_installer"
      chmod +x "$tmp_installer"
      if ! run_as_root sh "$tmp_installer"; then
        rm -f "$tmp_installer"
        err "Failed to install Ollama automatically."
        err "Install manually from https://ollama.com/download and rerun installer."
        exit 1
      fi
      rm -f "$tmp_installer"
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

ensure_playit() {
  if [[ "${PLAYIT_ENABLED,,}" != "true" ]]; then
    return
  fi

  if ! need_cmd playit; then
    log "Playit not found. Installing playit agent..."
    if [[ "$PLATFORM" == "linux" ]]; then
      local arch
      arch="$(uname -m)"
      local asset="playit-linux-amd64"
      case "$arch" in
        aarch64|arm64) asset="playit-linux-aarch64" ;;
        armv7l) asset="playit-linux-armv7" ;;
        i386|i686) asset="playit-linux-i686" ;;
      esac
      local url="https://github.com/playit-cloud/playit-agent/releases/latest/download/${asset}"
      mkdir -p "$HOME/.local/bin"
      curl -fL "$url" -o "$HOME/.local/bin/playit"
      chmod +x "$HOME/.local/bin/playit"
      if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        log "Playit installed to ~/.local/bin/playit (add ~/.local/bin to PATH if needed)."
      fi
    elif [[ "$PLATFORM" == "macos" ]]; then
      err "Auto-install for Playit on macOS is not configured yet. Install from https://playit.gg/download"
      exit 1
    else
      err "Unsupported OS for automatic Playit install in install.sh."
      exit 1
    fi
  fi

  log "Playit enabled. Complete tunnel claim after install using: arx tunnel setup"
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

  # Context size is no longer an interactive setup prompt.
  # Default is safe (4096). Advanced users can tune later with: arx ai set-context <tokens>
  if [[ -z "$GEMMA_CONTEXT_SIZE" ]]; then
    GEMMA_CONTEXT_SIZE="4096"
  fi
  if ! [[ "$GEMMA_CONTEXT_SIZE" =~ ^[0-9]+$ ]]; then
    err "Context size must be numeric."
    exit 1
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

  if [[ -z "$PLAYIT_ENABLED" ]]; then
    PLAYIT_ENABLED="false"
    if [[ "$YES_MODE" == false ]]; then
      _pe="$(select_from_list "Public Internet Access" "default" 0 "false (LAN only)" "true (use Playit tunnel)")"
      if [[ "$_pe" == true* ]]; then
        PLAYIT_ENABLED="true"
      else
        PLAYIT_ENABLED="false"
      fi
    fi
  fi

  if [[ "${PLAYIT_ENABLED,,}" == "true" && -z "$PLAYIT_URL" && "$YES_MODE" == false ]]; then
    _pu="$(prompt_with_art "Playit URL" "default" "Optional existing Playit public URL (leave blank to set up later): ")"
    PLAYIT_URL="${_pu:-}"
  fi

  if [[ -z "$ADMIN_USER" ]]; then
    ADMIN_USER="admin"
    if [[ "$YES_MODE" == false ]]; then
      _u="$(prompt_with_art "Admin Account" "admin" "Admin username [admin]: ")"
      ADMIN_USER="${_u:-admin}"
    fi
  fi

  # Password is always explicit now (no hidden auto-generated fallback prompt).
  if [[ -z "$ADMIN_PASS" ]]; then
    if [[ "$YES_MODE" == false ]]; then
      _pw="$(prompt_with_art "Admin Account" "admin" "Admin password (required, min 8 chars): ")"
      ADMIN_PASS="${_pw:-}"
    fi
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
  if [[ -z "$ARX_ADMIN_PASS" ]]; then err "Admin password is required. Provide one during setup or pass --admin-pass."; exit 1; fi
  if (( ${#ARX_ADMIN_PASS} < 8 )); then err "Admin password must be at least 8 characters."; exit 1; fi

  if ! [[ "$GEMMA_CONTEXT_SIZE" =~ ^[0-9]+$ ]]; then err "Context size must be numeric."; exit 1; fi
  if (( GEMMA_CONTEXT_SIZE < 1024 || GEMMA_CONTEXT_SIZE > 32768 )); then err "Context size must be 1024..32768."; exit 1; fi

  if ! [[ "$GEMMA_TEMPERATURE" =~ ^[0-9]+([.][0-9]+)?$ ]]; then err "Temperature must be numeric 0..2."; exit 1; fi
  awk -v t="$GEMMA_TEMPERATURE" 'BEGIN{exit (t>=0 && t<=2)?0:1}' || { err "Temperature must be 0..2"; exit 1; }

  if ! [[ "$MC_VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then err "Minecraft version must look like 1.20.4"; exit 1; fi

  PLAYIT_ENABLED="$(echo "$PLAYIT_ENABLED" | tr '[:upper:]' '[:lower:]')"
  if [[ "$PLAYIT_ENABLED" != "true" && "$PLAYIT_ENABLED" != "false" ]]; then
    err "PLAYIT_ENABLED must be true or false"
    exit 1
  fi
}

show_summary() {
  box "Setup Summary"
  echo "  Platform         : $PLATFORM"
  echo "  Dashboard port   : $DASHBOARD_PORT"
  echo "  Trigger          : $AGENT_TRIGGER"
  echo "  Gemma model      : $GEMMA_MODEL"
  echo "  Temperature      : $GEMMA_TEMPERATURE"
  echo "  Minecraft ver    : $MC_VERSION"
  echo "  Playit enabled   : $PLAYIT_ENABLED"
  if [[ -n "$PLAYIT_URL" ]]; then
    echo "  Playit URL       : $PLAYIT_URL"
  fi
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
  ARX_PLAYIT_ENABLED="$PLAYIT_ENABLED" \
  ARX_PLAYIT_URL="$PLAYIT_URL" \
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
  'gemma_context_size': int(os.environ.get('GEMMA_CONTEXT_SIZE','4096')),
  'gemma_temperature': float(os.environ.get('GEMMA_TEMPERATURE','0.2')),
  'gemma_max_reply_chars': 220,
  'gemma_cooldown_sec': 2.5,
  'playit_enabled': os.environ.get('PLAYIT_ENABLED','false').lower() == 'true',
  'playit_url': os.environ.get('PLAYIT_URL',''),
}
p.write_text(json.dumps(obj, indent=2), encoding='utf-8')
print('Wrote state/arx_config.json')
PY
}

finalize() {
  chmod +x app/minecraft_server/start.sh scripts/start_dashboard.sh install.sh scripts/generate_env.py scripts/arx_cli.py || true

  if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "macos" ]]; then
    mkdir -p "$HOME/.local/bin"
    cat > "$HOME/.local/bin/arx" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/arx_cli.py" "\$@"
EOF
    chmod +x "$HOME/.local/bin/arx"
  fi

  if [[ "$PLATFORM" == "linux" && -w "/usr/local/bin" ]]; then
    cat > /usr/local/bin/arx <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/arx_cli.py" "\$@"
EOF
    chmod +x /usr/local/bin/arx || true
  fi

  box "Install Complete"
  echo "  Dashboard URL : http://localhost:${DASHBOARD_PORT}/"
  echo "  Start command : arx start"
  echo "  Help command  : arx help"
  echo "  Status        : arx status"
  echo "  Shutdown      : arx shutdown"
  echo "  Tunnel setup  : arx tunnel setup"
  echo "  Tunnel status : arx tunnel status"
  echo "  AI context    : arx ai set-context 4096"
  if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "macos" ]]; then
    echo "  ARX launcher  : $HOME/.local/bin/arx"
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
      echo "  PATH note     : add ~/.local/bin to PATH to run 'arx' directly"
    fi
  fi
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

export DASHBOARD_PORT AGENT_TRIGGER GEMMA_MODEL GEMMA_CONTEXT_SIZE GEMMA_TEMPERATURE MC_VERSION PLAYIT_ENABLED PLAYIT_URL

banner
intro_animation
transition "Opening setup"
box "Interactive First-Run"
prompt_if_needed
validate_inputs
show_summary

preflight_privileges

transition "Running installation pipeline"
run_step "Prerequisite checks" install_prereqs
run_step "Python environment" setup_python
run_step "Ollama + model readiness" ensure_ollama
run_step "Playit tunnel readiness" ensure_playit
run_step "Project directories" setup_files
run_step "Minecraft server jar" download_server_jar
run_step "Secure env generation" write_env
run_step "Runtime setup profile" write_runtime_setup
run_step "Finalize installer" finalize

if [[ "$UI_ENABLED" == true ]]; then
  transition "All done"
fi
