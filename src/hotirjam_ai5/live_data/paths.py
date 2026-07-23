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
    # Prefer bridge/ over bare cwd so a decoy ``cwd/HOTIRJAM/mnq_dom.ndjson``
    # cannot steal the live receiver journals under ``bridge/HOTIRJAM/``.
    return (
        cwd / "bridge",
        package_root / "bridge",
        cwd,
        package_root,
    )


def _journal_size(path: Path) -> int:
    try:
        return int(path.stat().st_size) if path.is_file() else -1
    except OSError:
        return -1


def _pick_user_data_dir(candidates: tuple[Path, ...]) -> Path | None:
    """Choose the UserDataDir that owns the live tick/DOM journals.

    Preference:
    1. Directory with a non-empty tick journal (live ticks prove the path).
    2. Else directory with a non-empty DOM journal.
    3. Else directory with any tick file (even empty).
    4. Else directory with any DOM file.
    Among equal tiers, prefer the larger journal (live bridge over decoys).
    """
    best: tuple[int, int, Path] | None = None
    for candidate in candidates:
        tick = candidate / HOTIRJAM_SUBDIR / TICK_FILENAME
        dom = candidate / HOTIRJAM_SUBDIR / DOM_FILENAME
        tick_size = _journal_size(tick)
        dom_size = _journal_size(dom)
        if tick_size > 0:
            tier, score = 3, tick_size
        elif dom_size > 0:
            tier, score = 2, dom_size
        elif tick_size == 0:
            tier, score = 1, 0
        elif dom_size == 0:
            tier, score = 0, 0
        else:
            continue
        rank = (tier, score, candidate)
        if best is None or rank[:2] > best[:2]:
            best = rank
    return None if best is None else best[2]


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
    picked = _pick_user_data_dir(candidates)
    if picked is not None:
        return picked.resolve()

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


def sibling_dom_path(tick_path: Path) -> Path:
    """DOM journal next to a tick journal (same HOTIRJAM folder)."""
    return (Path(tick_path).expanduser().resolve().parent / DOM_FILENAME).resolve()
