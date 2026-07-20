"""Tests for DomHealthMonitor."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.dom_health import DomHealthMonitor
from hotirjam_ai5.dashboard.models import ConnectionQuality, FeedStatus


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_initial_dom_health_disconnected() -> None:
    monitor = DomHealthMonitor(clock=FakeClock())
    snap = monitor.snapshot()
    assert snap.feed_status is FeedStatus.DISCONNECTED
    assert snap.connection_quality is ConnectionQuality.UNKNOWN
    assert snap.last_update_age_ms is None
    assert snap.update_rate == 0.0


def test_record_update_healthy_and_rate() -> None:
    clock = FakeClock(0.0)
    monitor = DomHealthMonitor(clock=clock)
    previous = monitor.record_update()
    assert previous is FeedStatus.DISCONNECTED
    assert monitor.feed_status is FeedStatus.HEALTHY
    assert monitor.snapshot().update_rate == pytest.approx(1.0)
    assert monitor.snapshot().peak_update_rate == pytest.approx(1.0)


def test_dom_stall_and_disconnect() -> None:
    clock = FakeClock(0.0)
    monitor = DomHealthMonitor(stall_seconds=2.0, disconnect_seconds=5.0, clock=clock)
    monitor.record_update()
    clock.now = 2.5
    assert monitor.evaluate() is FeedStatus.HEALTHY
    assert monitor.feed_status is FeedStatus.STALE
    clock.now = 6.0
    assert monitor.evaluate() is FeedStatus.STALE
    assert monitor.feed_status is FeedStatus.DISCONNECTED
