from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class StylePack:
    key: str
    title: str
    arx_logo: str
    delusion_sample: str
    tagline: str = "Agentic Runtime for eXecution"
    accent_char: str = "▸"
    border_chars: tuple = ("╭", "─", "╮", "│", "╰", "╯")


# ---------------------------------------------------------------------------
#  Delta Corps Priest 1 — primary branding (Unicode)
# ---------------------------------------------------------------------------
ARX_DELTA_CORPS = r"""
   ▄████████    ▄████████ ▀████    ▐████▀
  ███    ███   ███    ███   ███▌   ████▀
  ███    ███   ███    ███    ███  ▐███
  ███    ███  ▄███▄▄▄▄██▀    ▀███▄███▀
▀███████████ ▀▀███▀▀▀▀▀      ████▀██▄
  ███    ███ ▀███████████   ▐███  ▀███
  ███    ███   ███    ███  ▄███     ███▄
  ███    █▀    ███    ███ ████       ███▄
               ███    ███
""".strip("\n")

DELUSION_DELTA_CORPS = r"""
████████▄     ▄████████  ▄█       ███    █▄     ▄████████  ▄█   ▄██████▄   ███▄▄▄▄
███   ▀███   ███    ███ ███       ███    ███   ███    ███ ███  ███    ███  ███▀▀▀██▄
███    ███   ███    █▀  ███       ███    ███   ███    █▀  ███▌ ███    ███  ███   ███
███    ███  ▄███▄▄▄     ███       ███    ███   ███        ███▌ ███    ███  ███   ███
███    ███ ▀▀███▀▀▀     ███       ███    ███ ▀███████████ ███▌ ███    ███  ███   ███
███    ███   ███    █▄  ███       ███    ███          ███ ███  ███    ███  ███   ███
███   ▄███   ███    ███ ███▌    ▄ ███    ███    ▄█    ███ ███  ███    ███  ███   ███
████████▀    ██████████ █████▄▄██ ████████▀   ▄████████▀  █▀    ▀██████▀   ▀█   █▀
""".strip("\n")

# ---------------------------------------------------------------------------
#  Legacy underground style (preserved for backward compat)
# ---------------------------------------------------------------------------
ARX_UNDERGROUND_UNICODE = r"""
         _                   _     _      _
        / /\                /\ \ /_/\    /\ \
       / /  \              /  \ \\ \ \   \ \_\
      / / /\ \            / /\ \ \\ \ \__/ / /
     / / /\ \ \          / / /\ \_\\ \__ \/_/
    / / /  \ \ \        / / /_/ / / \/_/\__/\
   / / /___/ /\ \      / / /__\/ /   _/\/__\ \
  / / /_____/ /\ \    / / /_____/   / _/_/\ \ \
 / /_________/\ \ \  / / /\ \ \    / / /   \ \ \
/ / /_       __\ \_\/ / /  \ \ \  / / /    /_/ /
\_\___\     /____/_/\/_/    \_\/  \/_/     \_\/
""".strip("\n")

DELUSION_UNDERGROUND_UNICODE = r"""
██████╗ ███████╗██╗     ██╗   ██╗███████╗██╗ ██████╗ ███╗   ██╗
██╔══██╗██╔════╝██║     ██║   ██║██╔════╝██║██╔═══██╗████╗  ██║
██║  ██║█████╗  ██║     ██║   ██║███████╗██║██║   ██║██╔██╗ ██║
██║  ██║██╔══╝  ██║     ██║   ██║╚════██║██║██║   ██║██║╚██╗██║
██████╔╝███████╗███████╗╚██████╔╝███████║██║╚██████╔╝██║ ╚████║
╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
""".strip("\n")

# ---------------------------------------------------------------------------
#  DOS-safe (CP437 compatible)
# ---------------------------------------------------------------------------
ARX_UNDERGROUND_DOS = r"""
______   ______  __   __
|  _  \ /  __  \ \ \ / /
| | | | | /  \ |  \ V /
| | | | | |  | |   > <
| |/ /  | \__/ |  / . \
|___/    \____/  /_/ \_\
""".strip("\n")

DELUSION_UNDERGROUND_DOS = r"""
______  _____ _     _   _ _____ _____ _____ _   _
|  _  \|  ___| |   | | | /  ___|_   _|  _  | \ | |
| | | || |__ | |   | | | \ `--.  | | | | | |  \| |
| | | ||  __|| |   | | | |`--. \ | | | | | | . ` |
| |/ / | |___| |___| |_| /\__/ /_| |_\ \_/ / |\  |
|___/  \____/\_____/\___/\____/ \___/ \___/\_| \_/
""".strip("\n")

# ---------------------------------------------------------------------------
#  Minimal safe fallback
# ---------------------------------------------------------------------------
ARX_MINIMAL = r"""
   _   ___ __  __
  /_\ | _ \\ \/ /
 / _ \|   / >  <
/_/ \_\_|_\/_/\_\
""".strip("\n")

DELUSION_MINIMAL = r"""
    ____  ________    __  _______ ________  _   __
   / __ \/ ____/ /   / / / / ___//  _/ __ \/ | / /
  / / / / __/ / /   / / / /\__ \ / // / / /  |/ /
 / /_/ / /___/ /___/ /_/ /___/ // // /_/ / /|  /
/_____/_____/_____/\____//____/___/\____/_/ |_/
""".strip("\n")


# ---------------------------------------------------------------------------
#  Animation frames — line-by-line reveal of the Delta Corps logo
# ---------------------------------------------------------------------------

def _split_logo_lines(logo: str) -> list[str]:
    return logo.split("\n") if logo else []


def build_reveal_frames(logo: str, blank_lines: int = 0) -> list[str]:
    """Build progressive reveal frames for animated startup."""
    lines = _split_logo_lines(logo)
    if not lines:
        return [""]
    frames: list[str] = []
    for i in range(1, len(lines) + 1):
        pad = [""] * max(0, len(lines) - i + blank_lines)
        frames.append("\n".join(pad + lines[:i]))
    return frames


def build_fade_frames(logo: str) -> list[str]:
    """Build a simple character-density fade-in effect."""
    lines = _split_logo_lines(logo)
    if not lines:
        return [""]
    full = "\n".join(lines)
    # Phase 1: dots only
    phase1 = "\n".join(
        "".join("·" if c not in (" ", "\n") else c for c in line)
        for line in lines
    )
    # Phase 2: block chars
    phase2 = "\n".join(
        "".join("░" if c not in (" ", "\n") else c for c in line)
        for line in lines
    )
    # Phase 3: medium blocks
    phase3 = "\n".join(
        "".join("▓" if c not in (" ", "\n") else c for c in line)
        for line in lines
    )
    return [phase1, phase2, phase3, full]


# ---------------------------------------------------------------------------
#  Status indicators
# ---------------------------------------------------------------------------
SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
SPINNER_FRAMES_DOS = ("-", "\\", "|", "/")
PULSE_CHARS = ("●", "◉", "○", "◉")
PULSE_CHARS_DOS = ("*", "o", ".", "o")

STATUS_UP = "● UP"
STATUS_DOWN = "○ DOWN"
STATUS_UP_DOS = "[+] UP"
STATUS_DOWN_DOS = "[-] DOWN"


def spinner_cycle(unicode_ok: bool = True) -> itertools.cycle:
    return itertools.cycle(SPINNER_FRAMES if unicode_ok else SPINNER_FRAMES_DOS)


def pulse_cycle(unicode_ok: bool = True) -> itertools.cycle:
    return itertools.cycle(PULSE_CHARS if unicode_ok else PULSE_CHARS_DOS)


# ---------------------------------------------------------------------------
#  Box-drawing helpers
# ---------------------------------------------------------------------------

def box_line(text: str, width: int = 60, char: str = "─") -> str:
    pad = max(0, width - len(text) - 4)
    return f"╭{char} {text} {char * pad}╮"


def box_row(left: str, right: str = "", width: int = 60) -> str:
    inner = width - 4
    if right:
        gap = max(1, inner - len(left) - len(right))
        content = f"{left}{' ' * gap}{right}"
    else:
        content = left
    content = content[:inner].ljust(inner)
    return f"│ {content} │"


def box_bottom(width: int = 60, char: str = "─") -> str:
    return f"╰{char * (width - 2)}╯"


def box_separator(width: int = 60) -> str:
    return f"├{'─' * (width - 2)}┤"


# ---------------------------------------------------------------------------
#  Tagline
# ---------------------------------------------------------------------------
TAGLINE = "Agentic Runtime for eXecution"
TAGLINE_STYLED = "▸ Agentic Runtime for eXecution"


# ---------------------------------------------------------------------------
#  Style Packs
# ---------------------------------------------------------------------------

STYLE_PACKS: dict[str, StylePack] = {
    "underground": StylePack(
        key="underground",
        title="Delta Corps Priest",
        arx_logo=ARX_DELTA_CORPS,
        delusion_sample=DELUSION_DELTA_CORPS,
        tagline=TAGLINE,
        accent_char="▸",
    ),
    "classic": StylePack(
        key="classic",
        title="Classic Underground",
        arx_logo=ARX_UNDERGROUND_UNICODE,
        delusion_sample=DELUSION_UNDERGROUND_UNICODE,
        tagline=TAGLINE,
        accent_char="▸",
    ),
    "dos": StylePack(
        key="dos",
        title="Underground DOS",
        arx_logo=ARX_UNDERGROUND_DOS,
        delusion_sample=DELUSION_UNDERGROUND_DOS,
        tagline=TAGLINE,
        accent_char=">",
        border_chars=(".", "-", ".", "|", "'", "'"),
    ),
    "minimal": StylePack(
        key="minimal",
        title="Minimal ASCII",
        arx_logo=ARX_MINIMAL,
        delusion_sample=DELUSION_MINIMAL,
        tagline=TAGLINE,
        accent_char=">",
        border_chars=("+", "-", "+", "|", "+", "+"),
    ),
    "off": StylePack(
        key="off",
        title="Off",
        arx_logo="",
        delusion_sample="",
        tagline="",
        accent_char=">",
    ),
}


def get_style_pack(key: str) -> StylePack:
    normalized = (key or "").strip().lower()
    return STYLE_PACKS.get(normalized, STYLE_PACKS["underground"])
