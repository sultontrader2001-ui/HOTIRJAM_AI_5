"""Presentation-only version / commit helpers for the dashboard."""

from __future__ import annotations

import subprocess
from functools import lru_cache

from hotirjam_ai5 import __version__


@lru_cache(maxsize=1)
def package_version() -> str:
    """Return package version string for SYSTEM display."""
    return __version__ or "--"


@lru_cache(maxsize=1)
def git_commit_short() -> str:
    """Best-effort short git SHA for SYSTEM display (never fails the app)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        return "--"
    if result.returncode != 0:
        return "--"
    text = (result.stdout or "").strip()
    return text or "--"
