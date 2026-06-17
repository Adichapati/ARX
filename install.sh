#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
#  ARX installer  --  https://arxmc.studio
#
#  Runs two ways:
#    1. From a cloned checkout:   ./install.sh
#    2. Hosted one-liner:         curl -fsSL https://arxmc.studio/install.sh | bash
#
#  In one-liner (bootstrap) mode the script arrives over a pipe with no repo
#  around it, so it downloads the integrity-verified runtime bundle, unpacks it
#  into $ARX_INSTALL_DIR (default ~/ARX), and re-executes the real installer
#  with stdin reconnected to the terminal so the guided setup still works.
#  This mirrors the Windows install.ps1 bootstrap behaviour.
# ============================================================================

ARX_BOOTSTRAP_ZIP_URL="${ARX_BOOTSTRAP_ZIP_URL:-https://arxmc.studio/arx-runtime.zip}"
ARX_BOOTSTRAP_CHECKSUMS_URL="${ARX_BOOTSTRAP_CHECKSUMS_URL:-https://arxmc.studio/checksums.txt}"
ARX_INSTALL_DIR="${ARX_INSTALL_DIR:-$HOME/ARX}"

_bs_need() { command -v "$1" >/dev/null 2>&1; }
_bs_say()  { printf '\033[38;5;45m[ARX]\033[0m %s\n' "$*"; }
_bs_die()  { printf '\033[38;5;203m[ARX][ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

# Directory this script physically lives in. Empty when piped via curl|bash.
_bs_script_dir() {
  local src="${BASH_SOURCE[0]:-}"
  if [[ -z "$src" || "$src" == "bash" || "$src" == "sh" || ! -f "$src" ]]; then
    printf ''
    return 0
  fi
  ( cd "$(dirname "$src")" >/dev/null 2>&1 && pwd )
}

# A real checkout has these marker files; a bare pipe does not.
_bs_is_checkout() {
  local d="$1"
  [[ -n "$d" && -f "$d/requirements.txt" && -f "$d/scripts/generate_env.py" && -f "$d/install.sh" ]]
}

_bs_sha256() {
  if _bs_need sha256sum; then sha256sum "$1" | awk '{print $1}'
  elif _bs_need shasum; then shasum -a 256 "$1" | awk '{print $1}'
  elif _bs_need openssl; then openssl dgst -sha256 "$1" | awk '{print $NF}'
  else return 1; fi
}

_bs_fetch() {        # url dest
  if _bs_need curl; then curl -fsSL "$1" -o "$2"
  elif _bs_need wget; then wget -qO "$2" "$1"
  else return 1; fi
}

_bs_fetch_stdout() { # url
  if _bs_need curl; then curl -fsSL "$1"
  elif _bs_need wget; then wget -qO- "$1"
  else return 1; fi
}

# Pull the expected hash for a filename out of a checksums.txt body.
_bs_expected_hash() { # checksums_text target_name
  awk -v target="$2" '
    /^[[:space:]]*#/ { next }
    {
      hash = $1
      name = $2
      sub(/^\*/, "", name)
      if (name == target && hash ~ /^[0-9a-fA-F]{64}$/) { print tolower(hash); exit }
    }' <<<"$1"
}

_bs_extract() {      # zip dest
  mkdir -p "$2"
  if _bs_need unzip; then unzip -oq "$1" -d "$2"
  elif _bs_need python3; then python3 -m zipfile -e "$1" "$2"
  elif _bs_need bsdtar; then bsdtar -xf "$1" -C "$2"
  else return 1; fi
}

arx_bootstrap() {
  _bs_say "Bootstrap mode -- fetching verified runtime from ${ARX_BOOTSTRAP_ZIP_URL}"
  _bs_need curl || _bs_need wget || _bs_die "Need 'curl' or 'wget' to bootstrap ARX."

  local tmp_zip checksums target expected actual
  tmp_zip="$(mktemp "${TMPDIR:-/tmp}/arx-runtime.XXXXXX")" || _bs_die "Cannot create temp file."
  trap 'rm -f "${tmp_zip:-}"' EXIT

  _bs_fetch "$ARX_BOOTSTRAP_ZIP_URL" "$tmp_zip" || _bs_die "Failed to download runtime bundle."

  checksums="$(_bs_fetch_stdout "$ARX_BOOTSTRAP_CHECKSUMS_URL")" || _bs_die "Failed to download checksums."
  target="$(basename "${ARX_BOOTSTRAP_ZIP_URL%%\?*}")"
  expected="$(_bs_expected_hash "$checksums" "$target")"
  [[ -n "$expected" ]] || _bs_die "No checksum entry for '$target' in $ARX_BOOTSTRAP_CHECKSUMS_URL"
  actual="$(_bs_sha256 "$tmp_zip")" || _bs_die "No SHA-256 tool found (need sha256sum/shasum/openssl)."
  if [[ "${actual,,}" != "$expected" ]]; then
    _bs_die "Runtime bundle checksum mismatch (expected $expected, got ${actual,,}). Refusing to continue."
  fi
  _bs_say "Runtime bundle verified (sha256 ok)."

  mkdir -p "$ARX_INSTALL_DIR" || _bs_die "Cannot create install dir: $ARX_INSTALL_DIR"
  _bs_extract "$tmp_zip" "$ARX_INSTALL_DIR" || _bs_die "Failed to extract bundle (need unzip, python3, or bsdtar)."
  rm -f "$tmp_zip"; trap - EXIT

  local reentry="$ARX_INSTALL_DIR/install.sh"
  if [[ ! -f "$reentry" ]]; then
    reentry="$(find "$ARX_INSTALL_DIR" -maxdepth 3 -name install.sh -type f 2>/dev/null | head -n1)"
  fi
  [[ -f "$reentry" ]] || _bs_die "Bootstrap failed: install.sh not found after extraction."
  chmod +x "$reentry" 2>/dev/null || true

  _bs_say "Runtime installed to ${ARX_INSTALL_DIR}"
  _bs_say "Launching guided setup..."
  echo

  export ARX_BOOTSTRAPPED=1
  # Reconnect stdin to the controlling terminal so the interactive setup works
  # even though this script itself arrived over a pipe. Probe /dev/tty by
  # actually opening it -- a node can exist with no controlling terminal
  # (containers/CI), where the open fails with ENXIO.
  if [[ ! -t 0 ]] && { : </dev/tty; } 2>/dev/null; then
    exec bash "$reentry" "$@" </dev/tty
  fi
  exec bash "$reentry" "$@"
}

ARX_SCRIPT_DIR="$(_bs_script_dir)"
if ! _bs_is_checkout "$ARX_SCRIPT_DIR"; then
  arx_bootstrap "$@"
fi

ROOT_DIR="$ARX_SCRIPT_DIR"
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
OLLAMA_INSTALL_SH_URL="https://ollama.com/install.sh"
OLLAMA_INSTALL_SH_SHA256="25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f"

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
log() { printf '  %s[ARX]%s %s\n' "${C_ACCENT:-}" "${C_RESET:-}" "$*"; }
err() { printf '  %s[ARX][ERROR]%s %s\n' "${C_ERR:-}" "${C_RESET:-}" "$*" >&2; }

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

# ----------------------------------------------------------------------------
#  Palette + glyphs  (honours NO_COLOR, dumb terminals and non-UTF locales)
# ----------------------------------------------------------------------------
ESC=$'\033'
C_RESET=""; C_DIM=""; C_BOLD=""; C_ACCENT=""; C_OK=""; C_WARN=""; C_ERR=""; C_MUTE=""
ARX_USE_COLOR=false
if [[ "$UI_ENABLED" == true && -z "${NO_COLOR:-}" && "${TERM:-}" != "dumb" ]]; then
  ARX_USE_COLOR=true
  C_RESET="${ESC}[0m"; C_DIM="${ESC}[2m"; C_BOLD="${ESC}[1m"
  C_ACCENT="${ESC}[38;5;45m"   # cyan
  C_OK="${ESC}[38;5;48m"       # green
  C_WARN="${ESC}[38;5;214m"    # amber
  C_ERR="${ESC}[38;5;203m"     # red
  C_MUTE="${ESC}[38;5;245m"    # grey
fi

# Smooth cyan -> green ramp for the logo reveal (xterm-256 cube).
LOGO_GRAD=(51 50 50 49 48 48 47 46 46 46)

# Glyphs are assigned once the style is resolved (see set_glyphs below).
GL_ARROW=">"; GL_DOT="-"; GL_RULE="-"; GL_OK="OK"; GL_DONE="*"
BAR_FULL="#"; BAR_EMPTY="."; STEP_FULL="="; STEP_EMPTY="-"

STEP_TOTAL=11
STEP_CUR=0

supports_unicode() {
  if [[ "${ARX_FORCE_ASCII:-}" =~ ^(1|true|yes|on)$ ]]; then
    return 1
  fi

  local lang_hint="${LC_ALL:-${LANG:-}}"
  if [[ "${lang_hint,,}" == *"utf"* ]]; then
    return 0
  fi

  if need_cmd locale; then
    local cm
    cm="$(locale charmap 2>/dev/null || true)"
    if [[ "${cm,,}" == *"utf"* ]]; then
      return 0
    fi
  fi

  return 1
}

installer_state_style() {
  local state_file="$ROOT_DIR/state/arx_ui.json"
  if [[ ! -f "$state_file" ]]; then
    return 0
  fi

  sed -n 's/.*"style"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$state_file" | head -n1
}

resolve_installer_style() {
  # Allowed style values: underground|classic|dos|minimal|off
  local style="${ARX_STYLE:-}"
  if [[ -z "$style" ]]; then
    style="$(installer_state_style)"
  fi
  style="${style,,}"

  case "$style" in
    underground|classic|dos|minimal|off) ;;
    *) style="underground" ;;
  esac

  if [[ "$style" == "underground" || "$style" == "classic" ]] && ! supports_unicode; then
    style="minimal"
  fi

  printf '%s' "$style"
}

installer_logo() {
  local style="$1"
  case "$style" in
    underground|"")
      # Delta Corps Priest "ARX" -- shared with the arx CLI/TUI branding.
      cat <<'EOF'
   ▄████████    ▄████████ ▀████    ▐████▀
  ███    ███   ███    ███   ███▌   ████▀
  ███    ███   ███    ███    ███  ▐███
  ███    ███  ▄███▄▄▄▄██▀    ▀███▄███▀
▀███████████ ▀▀███▀▀▀▀▀      ████▀██▄
  ███    ███ ▀███████████   ▐███  ▀███
  ███    ███   ███    ███  ▄███     ███▄
  ███    █▀    ███    ███ ████       ███▄
EOF
      ;;
    classic)
      cat <<'EOF'
 █████╗ ██████╗ ██╗  ██╗
██╔══██╗██╔══██╗╚██╗██╔╝
███████║██████╔╝ ╚███╔╝
██╔══██║██╔══██╗ ██╔██╗
██║  ██║██║  ██║██╔╝ ██╗
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
EOF
      ;;
    dos)
      cat <<'EOF'
______   ______  __   __
|  _  \ /  __  \ \ \ / /
| | | | | /  \ |  \ V /
| | | | | |  | |   > <
| |/ /  | \__/ |  / . \
|___/    \____/  /_/ \_\
EOF
      ;;
    minimal)
      cat <<'EOF'
    ___    ____  _  __
   /   |  / __ \| |/ /
  / /| | / /_/ /   /
 / ___ |/ _, _/   |
/_/  |_/_/ |_/_/|_|
EOF
      ;;
    off)
      ;;
  esac
}

INSTALLER_STYLE="$(resolve_installer_style)"

# Promote glyphs to Unicode once we know the resolved style supports it.
set_glyphs() {
  case "$INSTALLER_STYLE" in
    underground|classic)
      GL_ARROW="▸"; GL_DOT="·"; GL_RULE="─"; GL_OK="✓"; GL_DONE="●"
      BAR_FULL="█"; BAR_EMPTY="░"; STEP_FULL="━"; STEP_EMPTY="╌"
      ;;
  esac
}
set_glyphs

RULE_WIDTH=44

# Repeat a (possibly multibyte) glyph N times. Multibyte-safe, unlike `tr`,
# which operates byte-by-byte and shreds UTF-8 box-drawing characters.
repeat() {
  local ch="$1" n="$2" out=""
  while (( n-- > 0 )); do out+="$ch"; done
  printf '%s' "$out"
}

# Print the logo with a per-line cyan->green gradient (plain when no color).
print_logo() {
  [[ "$INSTALLER_STYLE" == "off" ]] && return 0
  local i=0 line code
  while IFS= read -r line; do
    if [[ "$ARX_USE_COLOR" == true ]]; then
      code="${LOGO_GRAD[i]:-${LOGO_GRAD[$((${#LOGO_GRAD[@]} - 1))]}}"
      printf '  %s%s%s\n' "${ESC}[1;38;5;${code}m" "$line" "$C_RESET"
    else
      printf '  %s\n' "$line"
    fi
    i=$((i + 1))
  done < <(installer_logo "$INSTALLER_STYLE")
}

# Same as print_logo but reveals one line at a time for the splash.
print_logo_animated() {
  if [[ "$ARX_USE_COLOR" != true ]]; then print_logo; return 0; fi
  [[ "$INSTALLER_STYLE" == "off" ]] && return 0
  local i=0 line code
  while IFS= read -r line; do
    code="${LOGO_GRAD[i]:-${LOGO_GRAD[$((${#LOGO_GRAD[@]} - 1))]}}"
    printf '  %s%s%s\n' "${ESC}[1;38;5;${code}m" "$line" "$C_RESET"
    sleep 0.03
    i=$((i + 1))
  done < <(installer_logo "$INSTALLER_STYLE")
}

brand_tagline() {
  printf '  %s%s Agentic Runtime for eXecution%s\n' "$C_ACCENT" "$GL_ARROW" "$C_RESET"
  printf '  %s   local-first minecraft ops %s arxmc.studio%s\n' "$C_MUTE" "$GL_DOT" "$C_RESET"
}

banner() {
  if [[ -n "${TERM:-}" && "$UI_ENABLED" == true ]]; then
    clear || true
  fi
  echo
  print_logo
  echo
  brand_tagline
  echo
}

# Animated first-paint: logo reveal, tagline, and a short prep shimmer.
splash() {
  if [[ "$UI_ENABLED" != true ]]; then
    banner
    return 0
  fi
  clear || true
  echo
  print_logo_animated
  echo
  brand_tagline
  echo
  loader_bar "Guided setup"
}

loader_bar() {
  local label="$1" width=34 i fill rest pct
  if [[ "$UI_ENABLED" != true ]]; then
    return 0
  fi
  for i in $(seq 1 "$width"); do
    fill="$(repeat "$BAR_FULL" "$i")"
    rest="$(repeat "$BAR_EMPTY" "$((width - i))")"
    pct=$((i * 100 / width))
    printf '\r  %s%s%s%s%s  %s%3d%%%s' "$C_ACCENT" "$fill" "$C_DIM" "$rest" "$C_RESET" "$C_MUTE" "$pct" "$C_RESET"
    sleep 0.012
  done
  printf '\r%-72s\r' ''
  printf '  %s%s%s %s%s ready%s\n\n' "$C_OK" "$GL_OK" "$C_RESET" "$C_DIM" "$label" "$C_RESET"
}

ascii_divider() {
  local tag="${1:-default}"
  local label
  case "$tag" in
    port)    label="NETWORK" ;;
    trigger) label="AI AGENT" ;;
    model)   label="MODEL" ;;
    ctx)     label="CONTEXT" ;;
    temp)    label="TEMPERATURE" ;;
    admin)   label="CREDENTIALS" ;;
    *)       label="CONFIGURE" ;;
  esac
  printf '  %s%s%s %s%s%s\n\n' "$C_ACCENT" "$GL_ARROW" "$C_RESET" "$C_MUTE" "$label" "$C_RESET"
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
      printf '    [%d] %s\n' "$((i + 1))" "${options[$i]}"
    done
    echo
    while true; do
      read -rp "    Choose 1-${#options[@]} (default $((default_index + 1))): " REPLY
      if [[ -z "$REPLY" ]]; then
        printf '%s' "${options[$default_index]}"
        return 0
      fi
      if [[ "$REPLY" =~ ^[0-9]+$ ]] && (( REPLY >= 1 && REPLY <= ${#options[@]} )); then
        printf '%s' "${options[$((REPLY - 1))]}"
        return 0
      fi
      echo "    Invalid selection, try again."
    done
  fi

  while true; do
    banner
    box "$title"
    ascii_divider "$tag"
    printf '    %sUp/Down arrows, Enter to choose%s\n\n' "$C_DIM" "$C_RESET"

    local i
    for i in "${!options[@]}"; do
      if (( i == index )); then
        printf '    %s%s %s%s\n' "$C_ACCENT" "$GL_ARROW" "${options[$i]}" "$C_RESET"
      else
        printf '      %s%s%s\n' "$C_MUTE" "${options[$i]}" "$C_RESET"
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

box() {
  local title="$1"
  local pad=$((RULE_WIDTH - ${#title}))
  if (( pad < 1 )); then pad=1; fi
  local tail
  tail="$(repeat "$GL_RULE" "$pad")"
  echo
  printf '  %s%s%s %s%s %s%s%s\n' "$C_ACCENT" "$GL_RULE$GL_RULE$GL_RULE" "$C_RESET" "$C_BOLD" "$title" "$C_DIM" "$tail" "$C_RESET"
}

transition() {
  local text="$1"
  if [[ "$UI_ENABLED" == true ]]; then
    local dots=""
    for _ in 1 2 3; do
      dots+="$GL_DOT"
      printf '\r  %s[ARX]%s %s%s   ' "$C_ACCENT" "$C_RESET" "$text" "$dots"
      sleep 0.09
    done
    printf "\r%-72s\r" ""
  fi
  printf '  %s[ARX]%s %s\n' "$C_ACCENT" "$C_RESET" "$text"
}

spinner_run() {
  local label="$1"
  shift

  local tmp pid frames flen i
  tmp="$(mktemp)"
  if [[ "$BAR_FULL" == "█" ]]; then
    frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'; flen=10
  else
    frames='|/-\'; flen=4
  fi

  "$@" >"$tmp" 2>&1 &
  pid=$!
  i=0

  if [[ "$UI_ENABLED" == true ]]; then
    while kill -0 "$pid" 2>/dev/null; do
      local c="${frames:i%flen:1}"
      printf '\r    %s%s%s %s' "$C_ACCENT" "$c" "$C_RESET" "$label"
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
      printf '    %s%s%s %s\n' "$C_OK" "$GL_OK" "$C_RESET" "$label"
    else
      echo "  [ARX] $label: ok"
    fi
    rm -f "$tmp"
    return 0
  fi

  printf '    %s%s%s %s\n' "$C_ERR" "x" "$C_RESET" "$label" >&2
  err "$label failed"
  sed -n '1,200p' "$tmp" >&2 || true
  rm -f "$tmp"
  return 1
}

tick_step() {
  STEP_CUR=$((STEP_CUR + 1))
  local filled remaining fb eb
  filled=$((STEP_CUR))
  remaining=$((STEP_TOTAL - STEP_CUR))
  fb="$(repeat "$STEP_FULL" "$filled")"
  eb="$(repeat "$STEP_EMPTY" "$remaining")"
  printf '  %s%s%s%s%s  %s[%02d/%02d]%s %s\n' \
    "$C_OK" "$fb" "$C_DIM" "$eb" "$C_RESET" \
    "$C_MUTE" "$STEP_CUR" "$STEP_TOTAL" "$C_RESET" "$1"
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
      local actual_sha
      tmp_installer="$(mktemp)"
      curl -fsSL "$OLLAMA_INSTALL_SH_URL" -o "$tmp_installer"

      if need_cmd sha256sum; then
        actual_sha="$(sha256sum "$tmp_installer" | awk '{print $1}')"
      elif need_cmd shasum; then
        actual_sha="$(shasum -a 256 "$tmp_installer" | awk '{print $1}')"
      elif need_cmd openssl; then
        actual_sha="$(openssl dgst -sha256 "$tmp_installer" | awk '{print $NF}')"
      else
        rm -f "$tmp_installer"
        err "No SHA-256 tool found (sha256sum/shasum/openssl). Cannot verify Ollama installer integrity."
        exit 1
      fi

      if [[ "${actual_sha,,}" != "${OLLAMA_INSTALL_SH_SHA256,,}" ]]; then
        rm -f "$tmp_installer"
        err "Ollama installer checksum mismatch."
        err "Expected: $OLLAMA_INSTALL_SH_SHA256"
        err "Actual  : $actual_sha"
        err "Refusing to execute unverified installer."
        exit 1
      fi

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
  printf "    %-18s %s\n" "Platform" "$PLATFORM"
  printf "    %-18s %s\n" "Dashboard port" "$DASHBOARD_PORT"
  printf "    %-18s %s\n" "Trigger" "$AGENT_TRIGGER"
  printf "    %-18s %s\n" "Gemma model" "$GEMMA_MODEL"
  printf "    %-18s %s\n" "Temperature" "$GEMMA_TEMPERATURE"
  printf "    %-18s %s\n" "Minecraft ver" "$MC_VERSION"
  printf "    %-18s %s\n" "Playit enabled" "$PLAYIT_ENABLED"
  if [[ -n "$PLAYIT_URL" ]]; then
    printf "    %-18s %s\n" "Playit URL" "$PLAYIT_URL"
  fi
  printf "    %-18s %s\n" "Admin user" "$ARX_ADMIN_USER"
  echo
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

  ARX_BIND_HOST="127.0.0.1" \
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
  echo
  printf '    %s%s%s ARX is ready.%s\n' "$C_OK" "$GL_DONE" "$C_BOLD" "$C_RESET"
  printf '    %sDashboard%s  %s%shttp://localhost:%s/%s\n\n' "$C_MUTE" "$C_RESET" "$C_OK" "$C_BOLD" "${DASHBOARD_PORT}" "$C_RESET"
  printf '    %sNext steps%s\n' "$C_DIM" "$C_RESET"
  printf '      %s%s%s %-16s %s\n' "$C_ACCENT" "$GL_ARROW" "$C_RESET" "arx start" "${C_MUTE}launch all services${C_RESET}"
  printf '      %s%s%s %-16s %s\n' "$C_ACCENT" "$GL_ARROW" "$C_RESET" "arx status" "${C_MUTE}show service status${C_RESET}"
  printf '      %s%s%s %-16s %s\n' "$C_ACCENT" "$GL_ARROW" "$C_RESET" "arx help" "${C_MUTE}full command menu${C_RESET}"
  printf '      %s%s%s %-16s %s\n' "$C_ACCENT" "$GL_ARROW" "$C_RESET" "arx tunnel setup" "${C_MUTE}optional public access${C_RESET}"
  echo
  if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "macos" ]]; then
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
      printf '    %s!%s %sadd ~/.local/bin to PATH, or run %s%s\n' "$C_WARN" "$C_RESET" "$C_MUTE" "$HOME/.local/bin/arx" "$C_RESET"
      echo
    fi
  fi
  printf '    %sIn-game AI trigger word: %s%s%s\n' "$C_MUTE" "$C_BOLD" "${AGENT_TRIGGER}" "$C_RESET"
  echo
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

arx_main() {
  splash
  box "Guided first-run setup"
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
}

# Auto-run when executed directly. Set ARX_SOURCE_ONLY=1 to source the helper
# functions (banner/splash/progress) without running the installer -- used by
# the visual preview harness and tests.
if [[ "${ARX_SOURCE_ONLY:-}" != "1" ]]; then
  arx_main "$@"
fi
