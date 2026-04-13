from __future__ import annotations

import json
import os
from pathlib import Path

from .ascii_assets import StylePack, get_style_pack
from .terminal_caps import supports_unicode


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

    if style in {"underground", "dos", "minimal"}:
        if style == "underground" and not supports_unicode():
            return "minimal"
        return style

    # default/fallback
    return "underground" if supports_unicode() else "minimal"


def style_pack(root: Path, explicit: str | None = None) -> StylePack:
    return get_style_pack(resolve_style(root, explicit=explicit))


def set_style(root: Path, style: str) -> str:
    normalized = (style or "").strip().lower()
    if normalized not in {"underground", "dos", "minimal", "off"}:
        raise ValueError("style must be one of: underground, dos, minimal, off")
    state = load_ui_state(root)
    state["style"] = normalized
    save_ui_state(root, state)
    return normalized
