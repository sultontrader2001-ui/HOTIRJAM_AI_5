"""Canonical NinjaTrader tick file paths."""

from __future__ import annotations

import os
from pathlib import Path

TICK_FILENAME = "mnq_ticks.ndjson"
DOM_FILENAME = "mnq_dom.ndjson"
HOTIRJAM_SUBDIR = "HOTIRJAM"


def _candidate_user_data_dirs(home: Path) -> tuple[Path, ...]:
    """Ordered locations where NinjaTrader 8 UserDataDir commonly lives."""
    return (
        home / "Documents" / "NinjaTrader 8",
        home / "OneDrive" / "Documents" / "NinjaTrader 8",
        home / "OneDrive" / "Documenten" / "NinjaTrader 8",  # NL locale
        home / "NinjaTrader 8",
    )


def _bridge_host_user_data_dirs() -> tuple[Path, ...]:
    """Mac AI host / bridge receiver journals (parent of HOTIRJAM/).

    Live Validator on Mac often has no NinjaTrader install; bridge writes to
    ``{cwd}/HOTIRJAM`` or ``{repo}/bridge/HOTIRJAM``. Prefer an existing tick file.
    """
    cwd = Path.cwd()
    # live_data/paths.py → parents[3] == HOTIRJAM_AI_5 package root (…/src/../)
    package_root = Path(__file__).resolve().parents[3]
    return (
        cwd,
        cwd / "bridge",
        package_root / "bridge",
        package_root,
    )


def default_ninjatrader_user_data_dir() -> Path:
    """Resolve NinjaTrader UserDataDir (override, then common locations).

    Prefers a directory that already contains ``HOTIRJAM/mnq_ticks.ndjson`` so
    Python watches the same file NT01 / bridge receiver is appending to.
    """
    override = os.environ.get("HOTIRJAM_NINJATRADER_USER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    # Prefer existing journals: NT UserDataDir first, then Mac bridge out-dirs.
    candidates = _candidate_user_data_dirs(home) + _bridge_host_user_data_dirs()

    for candidate in candidates:
        tick_file = candidate / HOTIRJAM_SUBDIR / TICK_FILENAME
        if tick_file.is_file():
            return candidate.resolve()
        dom_file = candidate / HOTIRJAM_SUBDIR / DOM_FILENAME
        if dom_file.is_file():
            return candidate.resolve()

    for candidate in _candidate_user_data_dirs(home):
        if candidate.is_dir():
            return candidate.resolve()

    return _candidate_user_data_dirs(home)[0].resolve()


def default_tick_path(*, user_data_dir: Path | None = None) -> Path:
    """Default NT01 output: ``{UserDataDir}/HOTIRJAM/mnq_ticks.ndjson``."""
    base = user_data_dir or default_ninjatrader_user_data_dir()
    return (Path(base).expanduser() / HOTIRJAM_SUBDIR / TICK_FILENAME).resolve()


def default_dom_path(*, user_data_dir: Path | None = None) -> Path:
    """Default NT04 output: ``{UserDataDir}/HOTIRJAM/mnq_dom.ndjson``."""
    base = user_data_dir or default_ninjatrader_user_data_dir()
    return (Path(base).expanduser() / HOTIRJAM_SUBDIR / DOM_FILENAME).resolve()
