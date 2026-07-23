"""Live feed health tracking (Sprint 3).

Single responsibility: derive feed status, quality, ages, and rates from ticks.
No market prices, DOM, physics, or trading logic.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from hotirjam_ai5.dashboard.models import ConnectionQuality, FeedStatus
from hotirjam_ai5.live_data.tick import LiveTick

DEFAULT_STALL_SECONDS = 2.0
# Disconnect must be well above typical MNQ quiet gaps; short gaps are STALE only.
DEFAULT_DISCONNECT_SECONDS = 15.0
RATE_WINDOW_SECONDS = 1.0

# Connection quality thresholds (last tick age, milliseconds).
GOOD_AGE_MS = 250.0
FAIR_AGE_MS = 1000.0


@dataclass(frozen=True, slots=True)
class FeedHealthSnapshot:
    """Immutable feed-health metrics for one dashboard frame."""

    feed_status: FeedStatus
    connection_quality: ConnectionQuality
    last_tick_age_ms: float | None
    tick_delay_ms: float | None
    average_tick_rate: float
    peak_tick_rate: float


class FeedHealthMonitor:
    """Tracks feed health from accepted live ticks and elapsed time."""

    def __init__(
        self,
        *,
        stall_seconds: float = DEFAULT_STALL_SECONDS,
        disconnect_seconds: float = DEFAULT_DISCONNECT_SECONDS,
        clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], float] | None = None,
    ) -> None:
        if stall_seconds <= 0:
            raise ValueError("stall_seconds must be positive")
        if disconnect_seconds <= 0:
            raise ValueError("disconnect_seconds must be positive")
        if disconnect_seconds < stall_seconds:
            raise ValueError("disconnect_seconds must be >= stall_seconds")

        self._stall_seconds = stall_seconds
        self._disconnect_seconds = disconnect_seconds
        self._clock = clock or time.monotonic
        self._wall_clock = wall_clock or time.time
        self._started_at = self._clock()
        self._tick_count = 0
        self._last_tick_at: float | None = None
        self._last_tick_delay_ms: float | None = None
        self._peak_tick_rate = 0.0
        self._recent_ticks: deque[float] = deque()
        self._feed_status = FeedStatus.DISCONNECTED
        self._ever_connected = False

    @property
    def feed_status(self) -> FeedStatus:
        return self._feed_status

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def stall_seconds(self) -> float:
        return self._stall_seconds

    @property
    def disconnect_seconds(self) -> float:
        return self._disconnect_seconds

    def record_tick(self, tick: LiveTick) -> FeedStatus:
        """Record one live tick. Returns the new feed status."""
        now = self._clock()
        self._tick_count += 1
        self._last_tick_at = now
        self._last_tick_delay_ms = max(0.0, (self._wall_clock() - tick.timestamp) * 1000.0)
        self._recent_ticks.append(now)
        self._prune_recent(now)
        window_rate = self._window_rate(now)
        if window_rate > self._peak_tick_rate:
            self._peak_tick_rate = window_rate

        previous = self._feed_status
        self._feed_status = FeedStatus.HEALTHY
        self._ever_connected = True
        return previous

    def evaluate(self) -> FeedStatus:
        """Update status from elapsed time since the last tick.

        Returns the previous status (useful for transition logging).
        """
        previous = self._feed_status
        if self._last_tick_at is None:
            self._feed_status = FeedStatus.DISCONNECTED
            return previous

        age = self._clock() - self._last_tick_at
        if age >= self._disconnect_seconds:
            self._feed_status = FeedStatus.DISCONNECTED
        elif age >= self._stall_seconds:
            self._feed_status = FeedStatus.STALE
        else:
            self._feed_status = FeedStatus.HEALTHY
        return previous

    def snapshot(self) -> FeedHealthSnapshot:
        """Build one immutable health snapshot.

        Always re-evaluates from receive-age so ``feed_status`` cannot disagree
        with ``last_tick_age_ms`` when the caller skipped ``evaluate()``.
        """
        self.evaluate()
        now = self._clock()
        self._prune_recent(now)
        age_ms = None
        if self._last_tick_at is not None:
            age_ms = max(0.0, (now - self._last_tick_at) * 1000.0)

        return FeedHealthSnapshot(
            feed_status=self._feed_status,
            connection_quality=self._quality(age_ms),
            last_tick_age_ms=age_ms,
            tick_delay_ms=self._last_tick_delay_ms,
            average_tick_rate=self._average_rate(now),
            peak_tick_rate=self._peak_tick_rate,
        )

    def _average_rate(self, now: float) -> float:
        elapsed = max(0.0, now - self._started_at)
        if elapsed <= 0.0:
            return 0.0
        return self._tick_count / elapsed

    def _window_rate(self, now: float) -> float:
        self._prune_recent(now)
        if not self._recent_ticks:
            return 0.0
        return len(self._recent_ticks) / RATE_WINDOW_SECONDS

    def _prune_recent(self, now: float) -> None:
        cutoff = now - RATE_WINDOW_SECONDS
        while self._recent_ticks and self._recent_ticks[0] < cutoff:
            self._recent_ticks.popleft()

    def _quality(self, age_ms: float | None) -> ConnectionQuality:
        if self._feed_status is FeedStatus.DISCONNECTED or age_ms is None:
            if self._ever_connected:
                return ConnectionQuality.POOR
            return ConnectionQuality.UNKNOWN
        if self._feed_status is FeedStatus.STALE:
            return ConnectionQuality.POOR
        if age_ms <= GOOD_AGE_MS:
            return ConnectionQuality.GOOD
        if age_ms <= FAIR_AGE_MS:
            return ConnectionQuality.FAIR
        return ConnectionQuality.POOR
