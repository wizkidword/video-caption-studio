from __future__ import annotations

import sys
from pathlib import Path


def is_frozen_exe() -> bool:
    return bool(getattr(sys, "frozen", False))


def runtime_mode() -> str:
    return "exe" if is_frozen_exe() else "source"


def bundled_root() -> Path | None:
    if not is_frozen_exe():
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    return Path(meipass)
