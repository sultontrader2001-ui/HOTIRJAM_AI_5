"""Session statistics: tick count, tick rate, running time."""

from __future__ import annotations

import time
from collections.abc import Callable


class SessionStatistics:
    """Tracks runtime counters for the STATISTICS section.

    Tick rate is ticks per second over the elapsed session time.
    With no ticks, rate is 0.0 — not fabricated activity.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._started_at = self._clock()
        self._tick_count = 0

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def record_tick(self, count: int = 1) -> None:
        """Increment the tick counter. Does not invent market prices."""
        if count < 1:
            raise ValueError("count must be at least 1")
        self._tick_count += count

    def running_time_seconds(self) -> float:
        """Seconds since construction (or last reset)."""
        return max(0.0, self._clock() - self._started_at)

    def tick_rate(self) -> float:
        """Ticks per second over elapsed session time."""
        elapsed = self.running_time_seconds()
        if elapsed <= 0.0:
            return 0.0
        return self._tick_count / elapsed

    def reset(self) -> None:
        """Clear counters and restart the session clock."""
        self._tick_count = 0
        self._started_at = self._clock()
