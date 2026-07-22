"""Mission Control display formatting only (H-7.2A.1).

No binding / provenance / runtime changes — string layout helpers.
"""

from __future__ import annotations

import shutil

NA = "N/A"
UNKNOWN = "Unknown"
DASH = "--"

# Wall-clock epochs are ~1e9+; synthetic/relative stamps are much smaller.
_WALL_EPOCH_FLOOR = 1_000_000_000.0
_MAX_AGE_SECONDS = 7.0 * 24.0 * 3600.0  # 7 days

_SHORT_SOURCES = (
    "ValidatorFrame",
    "DashboardState",
    "LoopTiming",
    "Journal",
)


def terminal_width(*, fallback: int = 80) -> int:
    try:
        return max(40, shutil.get_terminal_size(fallback=(fallback, 24)).columns)
    except OSError:
        return fallback


def truncate(text: str, max_len: int) -> str:
    """Fit text into max_len columns; ellipsis when truncated."""
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def fit_line(text: str, width: int) -> str:
    """Clamp one terminal row to ``width`` (no overflow)."""
    return truncate(text.rstrip("\n"), max(1, width))


def short_source(source_object: str) -> str:
    """Cockpit-only source label (family name, not full path)."""
    raw = (source_object or "").strip()
    if not raw or raw == "none":
        return NA
    lower = raw.lower()
    if "validatorframe" in lower.replace("_", "") or raw.startswith("ValidatorFrame"):
        return "ValidatorFrame"
    if "dashboardstate" in lower.replace("_", "") or raw.startswith("DashboardState"):
        return "DashboardState"
    if "looptiming" in lower.replace("_", "") or "LoopTiming" in raw:
        return "LoopTiming"
    if "journal" in lower or raw.startswith("structural_transition"):
        return "Journal"
    if "runtime" in lower:
        return NA
    # First path segment only, then map known roots.
    root = raw.split(".", 1)[0]
    for name in _SHORT_SOURCES:
        if root == name or root.startswith(name):
            return name
    return truncate(root, 16)


def format_age_display(now: float, timestamp: float | None) -> str:
    """Safe age for UI. Impossible / non-comparable stamps → N/A / -- / Unknown."""
    if timestamp is None:
        return NA
    if not isinstance(timestamp, (int, float)):
        return UNKNOWN
    # Mismatched time domains (wall vs relative synthetic).
    if now >= _WALL_EPOCH_FLOOR and float(timestamp) < _WALL_EPOCH_FLOOR:
        return NA
    if float(timestamp) >= _WALL_EPOCH_FLOOR and now < _WALL_EPOCH_FLOOR:
        return NA
    age = float(now) - float(timestamp)
    if age < 0:
        return NA
    if age > _MAX_AGE_SECONDS:
        return NA
    if age < 1.0:
        return f"{age * 1000.0:.0f}ms"
    if age < 60.0:
        return f"{age:.1f}s"
    if age < 3600.0:
        return f"{age / 60.0:.1f}m"
    if age < 86400.0:
        return f"{age / 3600.0:.1f}h"
    return DASH


def clamp_lines(lines: list[str], width: int) -> list[str]:
    """Apply column clamp to every line once (no duplication)."""
    return [fit_line(line, width) for line in lines]


def dedupe_consecutive(lines: list[str]) -> list[str]:
    """Drop exact consecutive duplicate rows (repeated render artifact)."""
    out: list[str] = []
    prev: str | None = None
    for line in lines:
        if line == prev:
            continue
        out.append(line)
        prev = line
    return out
