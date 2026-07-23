"""Heartbeat monitor skeleton (Sprint 1 — no network)."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_gateway.health import HealthStatus
from hotirjam_gateway.logging import get_logger

_log = get_logger(__name__)


class HeartbeatMonitor:
    """Track heartbeat freshness for Gateway health.

    Sprint 1: local bookkeeping only. Transport send/receive is later.
    """

    def __init__(
        self,
        *,
        interval_s: float = 1.0,
        stale_after_s: float = 5.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be > 0")
        if stale_after_s <= 0:
            raise ValueError("stale_after_s must be > 0")
        self.interval_s = float(interval_s)
        self.stale_after_s = float(stale_after_s)
        self._clock = clock or time.monotonic
        self._last_ok_at: float | None = None
        self._beat_count = 0

    @property
    def beat_count(self) -> int:
        return self._beat_count

    @property
    def last_ok_at(self) -> float | None:
        return self._last_ok_at

    def record_success(self) -> None:
        """Record a successful heartbeat exchange."""
        self._last_ok_at = float(self._clock())
        self._beat_count += 1
        _log.debug(
            "heartbeat_ok",
            extra={"gateway_event": "heartbeat_ok", "hb_ok": True},
        )

    def age_s(self) -> float | None:
        """Seconds since last successful beat, or None if never."""
        if self._last_ok_at is None:
            return None
        return max(0.0, float(self._clock()) - self._last_ok_at)

    def is_ok(self) -> bool:
        age = self.age_s()
        if age is None:
            return False
        return age <= self.stale_after_s

    def health_contribution(self) -> HealthStatus:
        """Map heartbeat freshness to a health contribution.

        Never observed → UNHEALTHY; stale → DEGRADED; fresh → HEALTHY.
        """
        if self._last_ok_at is None:
            return HealthStatus.UNHEALTHY
        if self.is_ok():
            return HealthStatus.HEALTHY
        return HealthStatus.DEGRADED

    def reset(self) -> None:
        self._last_ok_at = None
        self._beat_count = 0
