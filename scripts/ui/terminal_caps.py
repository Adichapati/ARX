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


def terminal_width(default: int = 80) -> int:
    try:
        import shutil

        return int(shutil.get_terminal_size((default, 24)).columns)
    except Exception:
        return default


def can_animate() -> bool:
    if os.environ.get("ARX_REDUCE_MOTION", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return sys.stdout.isatty()
