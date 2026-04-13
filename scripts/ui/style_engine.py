from __future__ import annotations

import json
import os
from pathlib import Path

from .ascii_assets import StylePack, get_style_pack
from .terminal_caps import supports_unicode


# ---------------------------------------------------------------------------
#  Theme color palettes  (TUI + CLI)
# ---------------------------------------------------------------------------

THEME_PALETTES: dict[str, dict[str, str]] = {
    "neon_underground": {
        "bg": "#080c12",
        "surface": "#0f1520",
        "surface_bright": "#161f2e",
        "border": "#1e3048",
        "border_focus": "#38bdf8",
        "primary": "#38bdf8",
        "secondary": "#6ee7b7",
        "accent": "#f59e0b",
        "text": "#e2e8f0",
        "text_muted": "#64748b",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "info": "#38bdf8",
        "banner": "#38bdf8",
        "tagline": "#6ee7b7",
        "card_bg": "#111827",
        "card_border": "#1e3a5f",
        "scrollbar": "#1e3048",
        "scrollbar_hover": "#38bdf8",
    },
    "classic_dark": {
        "bg": "#0d0d0d",
        "surface": "#181818",
        "surface_bright": "#222222",
        "border": "#333333",
        "border_focus": "#70d6ff",
        "primary": "#70d6ff",
        "secondary": "#a8e6cf",
        "accent": "#ffd166",
        "text": "#e8e8e8",
        "text_muted": "#888888",
        "success": "#4caf50",
        "warning": "#ffd166",
        "error": "#ff6b6b",
        "info": "#70d6ff",
        "banner": "#70d6ff",
        "tagline": "#a8e6cf",
        "card_bg": "#1a1a1a",
        "card_border": "#444444",
        "scrollbar": "#333333",
        "scrollbar_hover": "#70d6ff",
    },
    "mono": {
        "bg": "#0a0a0a",
        "surface": "#141414",
        "surface_bright": "#1e1e1e",
        "border": "#3a3a3a",
        "border_focus": "#c0c0c0",
        "primary": "#d4d4d4",
        "secondary": "#b0b0b0",
        "accent": "#e0e0e0",
        "text": "#e8e8e8",
        "text_muted": "#777777",
        "success": "#a0a0a0",
        "warning": "#d0d0d0",
        "error": "#ffffff",
        "info": "#c0c0c0",
        "banner": "#e0e0e0",
        "tagline": "#b0b0b0",
        "card_bg": "#151515",
        "card_border": "#4a4a4a",
        "scrollbar": "#3a3a3a",
        "scrollbar_hover": "#d4d4d4",
    },
}

AVAILABLE_THEMES = tuple(THEME_PALETTES.keys())


def get_palette(theme: str) -> dict[str, str]:
    return THEME_PALETTES.get(theme, THEME_PALETTES["neon_underground"])


# ---------------------------------------------------------------------------
#  State persistence
# ---------------------------------------------------------------------------

def _state_file(root: Path) -> Path:
    return root / "state" / "arx_ui.json"


def load_ui_state(root: Path) -> dict:
    path = _state_file(root)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def save_ui_state(root: Path, state: dict) -> None:
    path = _state_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
#  Style resolution
# ---------------------------------------------------------------------------

def resolve_style(root: Path, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        style = explicit.strip().lower()
    else:
        env_style = os.environ.get("ARX_STYLE", "").strip().lower()
        if env_style:
            style = env_style
        else:
            state = load_ui_state(root)
            style = str(state.get("style", "underground")).strip().lower() or "underground"

    if style == "off":
        return "off"

    if style in {"underground", "classic", "dos", "minimal"}:
        if style in {"underground", "classic"} and not supports_unicode():
            return "minimal"
        return style

    # default/fallback
    return "underground" if supports_unicode() else "minimal"


def style_pack(root: Path, explicit: str | None = None) -> StylePack:
    return get_style_pack(resolve_style(root, explicit=explicit))


def set_style(root: Path, style: str) -> str:
    normalized = (style or "").strip().lower()
    if normalized not in {"underground", "classic", "dos", "minimal", "off"}:
        raise ValueError("style must be one of: underground, classic, dos, minimal, off")
    state = load_ui_state(root)
    state["style"] = normalized
    save_ui_state(root, state)
    return normalized


# ---------------------------------------------------------------------------
#  Theme resolution
# ---------------------------------------------------------------------------

def resolve_theme(root: Path) -> str:
    env_theme = os.environ.get("ARX_TUI_THEME", "").strip().lower()
    if env_theme in AVAILABLE_THEMES:
        return env_theme
    state = load_ui_state(root)
    state_theme = str(state.get("theme", "")).strip().lower()
    if state_theme in AVAILABLE_THEMES:
        return state_theme
    return "neon_underground"


def next_theme(current: str) -> str:
    c = (current or "").strip().lower()
    if c not in AVAILABLE_THEMES:
        return AVAILABLE_THEMES[0]
    idx = AVAILABLE_THEMES.index(c)
    return AVAILABLE_THEMES[(idx + 1) % len(AVAILABLE_THEMES)]
