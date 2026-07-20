"""DOM feed health tracking (Sprint 4).

Tracks DOM update freshness and update rate. No physics or trading logic.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from hotirjam_ai5.dashboard.models import ConnectionQuality, FeedStatus

DEFAULT_STALL_SECONDS = 2.0
DEFAULT_DISCONNECT_SECONDS = 5.0
RATE_WINDOW_SECONDS = 1.0

GOOD_AGE_MS = 250.0
FAIR_AGE_MS = 1000.0


@dataclass(frozen=True, slots=True)
class DomHealthSnapshot:
    """Immutable DOM-health metrics for one dashboard frame."""

    feed_status: FeedStatus
    connection_quality: ConnectionQuality
    last_update_age_ms: float | None
    update_rate: float
    peak_update_rate: float


class DomHealthMonitor:
    """Tracks DOM health from accepted snapshots and elapsed time."""

    def __init__(
        self,
        *,
        stall_seconds: float = DEFAULT_STALL_SECONDS,
        disconnect_seconds: float = DEFAULT_DISCONNECT_SECONDS,
        clock: Callable[[], float] | None = None,
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
        self._started_at = self._clock()
        self._update_count = 0
        self._last_update_at: float | None = None
        self._peak_update_rate = 0.0
        self._recent_updates: deque[float] = deque()
        self._feed_status = FeedStatus.DISCONNECTED
        self._ever_connected = False

    @property
    def feed_status(self) -> FeedStatus:
        return self._feed_status

    @property
    def update_count(self) -> int:
        return self._update_count

    def record_update(self) -> FeedStatus:
        """Record one accepted DOM snapshot. Returns previous status."""
        now = self._clock()
        self._update_count += 1
        self._last_update_at = now
        self._recent_updates.append(now)
        self._prune_recent(now)
        window_rate = self._window_rate(now)
        if window_rate > self._peak_update_rate:
            self._peak_update_rate = window_rate

        previous = self._feed_status
        self._feed_status = FeedStatus.HEALTHY
        self._ever_connected = True
        return previous

    def evaluate(self) -> FeedStatus:
        """Update status from elapsed time since the last DOM snapshot."""
        previous = self._feed_status
        if self._last_update_at is None:
            self._feed_status = FeedStatus.DISCONNECTED
            return previous

        age = self._clock() - self._last_update_at
        if age >= self._disconnect_seconds:
            self._feed_status = FeedStatus.DISCONNECTED
        elif age >= self._stall_seconds:
            self._feed_status = FeedStatus.STALE
        else:
            self._feed_status = FeedStatus.HEALTHY
        return previous

    def snapshot(self) -> DomHealthSnapshot:
        now = self._clock()
        self._prune_recent(now)
        age_ms = None
        if self._last_update_at is not None:
            age_ms = max(0.0, (now - self._last_update_at) * 1000.0)

        return DomHealthSnapshot(
            feed_status=self._feed_status,
            connection_quality=self._quality(age_ms),
            last_update_age_ms=age_ms,
            update_rate=self._window_rate(now),
            peak_update_rate=self._peak_update_rate,
        )

    def _window_rate(self, now: float) -> float:
        self._prune_recent(now)
        if not self._recent_updates:
            return 0.0
        return len(self._recent_updates) / RATE_WINDOW_SECONDS

    def _prune_recent(self, now: float) -> None:
        cutoff = now - RATE_WINDOW_SECONDS
        while self._recent_updates and self._recent_updates[0] < cutoff:
            self._recent_updates.popleft()

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
