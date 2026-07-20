"""Canonical NinjaTrader tick file paths."""

from __future__ import annotations

import os
from pathlib import Path

TICK_FILENAME = "mnq_ticks.ndjson"
HOTIRJAM_SUBDIR = "HOTIRJAM"


def _candidate_user_data_dirs(home: Path) -> tuple[Path, ...]:
    """Ordered locations where NinjaTrader 8 UserDataDir commonly lives."""
    return (
        home / "Documents" / "NinjaTrader 8",
        home / "OneDrive" / "Documents" / "NinjaTrader 8",
        home / "OneDrive" / "Documenten" / "NinjaTrader 8",  # NL locale
        home / "NinjaTrader 8",
    )


def default_ninjatrader_user_data_dir() -> Path:
    """Resolve NinjaTrader UserDataDir (override, then common locations).

    Prefers a directory that already contains ``HOTIRJAM/mnq_ticks.ndjson`` so
    Python watches the same file NT01 is appending to.
    """
    override = os.environ.get("HOTIRJAM_NINJATRADER_USER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    candidates = _candidate_user_data_dirs(home)

    for candidate in candidates:
        tick_file = candidate / HOTIRJAM_SUBDIR / TICK_FILENAME
        if tick_file.is_file():
            return candidate.resolve()

    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()

    return candidates[0].resolve()


def default_tick_path(*, user_data_dir: Path | None = None) -> Path:
    """Default NT01 output: ``{UserDataDir}/HOTIRJAM/mnq_ticks.ndjson``."""
    base = user_data_dir or default_ninjatrader_user_data_dir()
    return (Path(base).expanduser() / HOTIRJAM_SUBDIR / TICK_FILENAME).resolve()
