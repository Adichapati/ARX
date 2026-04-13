from __future__ import annotations

import os
import sys


def supports_unicode() -> bool:
    env = os.environ.get("ARX_FORCE_ASCII", "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return False

    encoding = (sys.stdout.encoding or "").lower()
    if "utf" in encoding:
        return True

    lang = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    return "utf" in lang.lower()


def supports_truecolor() -> bool:
    """Detect if terminal supports 24-bit / true-color."""
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in {"truecolor", "24bit"}:
        return True
    term = os.environ.get("TERM", "").lower()
    if "256color" in term or "truecolor" in term:
        return True
    # Windows Terminal and modern terminals support it
    if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") in (
        "vscode",
        "iTerm.app",
        "WezTerm",
        "Hyper",
    ):
        return True
    return False


def terminal_width(default: int = 80) -> int:
    try:
        import shutil

        return int(shutil.get_terminal_size((default, 24)).columns)
    except Exception:
        return default


def terminal_height(default: int = 24) -> int:
    try:
        import shutil

        return int(shutil.get_terminal_size((80, default)).lines)
    except Exception:
        return default


def can_animate() -> bool:
    if os.environ.get("ARX_REDUCE_MOTION", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return sys.stdout.isatty()


def optimal_fps() -> float:
    """Return a safe animation FPS for the current terminal."""
    if not can_animate():
        return 0.0
    # Windows cmd.exe is slower to flush; be conservative
    if os.name == "nt" and not os.environ.get("WT_SESSION"):
        return 10.0
    return 20.0


def is_narrow(threshold: int = 90) -> bool:
    return terminal_width() < threshold
