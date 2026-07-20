"""Canonical NinjaTrader tick file paths."""

from __future__ import annotations

import os
from pathlib import Path

TICK_FILENAME = "mnq_ticks.ndjson"
HOTIRJAM_SUBDIR = "HOTIRJAM"


def default_ninjatrader_user_data_dir() -> Path:
    """Resolve NinjaTrader UserDataDir (override, then common locations)."""
    override = os.environ.get("HOTIRJAM_NINJATRADER_USER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    home = Path.home()
    candidates = (
        home / "Documents" / "NinjaTrader 8",
        home / "NinjaTrader 8",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def default_tick_path(*, user_data_dir: Path | None = None) -> Path:
    """Default NT01 output: ``{UserDataDir}/HOTIRJAM/mnq_ticks.ndjson``."""
    base = user_data_dir or default_ninjatrader_user_data_dir()
    return base / HOTIRJAM_SUBDIR / TICK_FILENAME
