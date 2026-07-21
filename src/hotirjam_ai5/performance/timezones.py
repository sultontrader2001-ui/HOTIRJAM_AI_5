"""Multi-timezone timestamp helpers for Performance Tracker."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from hotirjam_ai5.performance.models import MultiZoneTimestamp

UTC = timezone.utc
NEW_YORK = ZoneInfo("America/New_York")
TASHKENT = ZoneInfo("Asia/Tashkent")


def format_multi_zone(epoch_seconds: float) -> MultiZoneTimestamp:
    """Format one UTC epoch as UTC / New York / Tashkent strings."""
    instant = datetime.fromtimestamp(epoch_seconds, tz=UTC)
    ny = instant.astimezone(NEW_YORK)
    tashkent = instant.astimezone(TASHKENT)
    ny_abbr = ny.tzname() or "ET"
    return MultiZoneTimestamp(
        utc=instant.strftime("%Y-%m-%d %H:%M:%S"),
        new_york=f"{ny.strftime('%Y-%m-%d %H:%M:%S')} {ny_abbr}",
        tashkent=f"{tashkent.strftime('%Y-%m-%d %H:%M:%S')} UZT",
        epoch_seconds=epoch_seconds,
    )
