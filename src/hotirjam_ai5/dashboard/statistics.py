"""Session statistics: tick count, tick rate, running time, decisions."""

from __future__ import annotations

import time
from collections.abc import Callable


class SessionStatistics:
    """Tracks runtime tick and decision counters for STATISTICS.

    Tick rate is ticks per second over the elapsed session time.
    With no ticks, rate is 0.0 — not fabricated activity.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._started_at = self._clock()
        self._tick_count = 0
        self._buy_internal_count = 0
        self._sell_internal_count = 0
        self._no_trade_count = 0

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def record_tick(self, count: int = 1) -> None:
        """Increment the tick counter. Does not invent market prices."""
        if count < 1:
            raise ValueError("count must be at least 1")
        self._tick_count += count

    @property
    def buy_internal_count(self) -> int:
        return self._buy_internal_count

    @property
    def sell_internal_count(self) -> int:
        return self._sell_internal_count

    @property
    def no_trade_count(self) -> int:
        return self._no_trade_count

    @property
    def decision_count(self) -> int:
        return (
            self._buy_internal_count
            + self._sell_internal_count
            + self._no_trade_count
        )

    def record_decision(self, decision: str) -> None:
        """Count one observation-only Trade Decision result."""
        if decision == "BUY_INTERNAL":
            self._buy_internal_count += 1
            return
        if decision == "SELL_INTERNAL":
            self._sell_internal_count += 1
            return
        if decision == "NO_TRADE":
            self._no_trade_count += 1
            return
        raise ValueError(f"unsupported decision: {decision}")

    def decision_frequency(self, decision: str) -> float:
        """Return a decision's percentage of all evaluated decisions."""
        total = self.decision_count
        if total == 0:
            return 0.0
        if decision == "BUY_INTERNAL":
            count = self._buy_internal_count
        elif decision == "SELL_INTERNAL":
            count = self._sell_internal_count
        elif decision == "NO_TRADE":
            count = self._no_trade_count
        else:
            raise ValueError(f"unsupported decision: {decision}")
        return (count / total) * 100.0

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
        self._buy_internal_count = 0
        self._sell_internal_count = 0
        self._no_trade_count = 0
        self._started_at = self._clock()
