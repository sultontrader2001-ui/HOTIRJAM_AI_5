"""Tests for FeedHealthMonitor."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.feed_health import FeedHealthMonitor
from hotirjam_ai5.dashboard.models import ConnectionQuality, FeedStatus
from hotirjam_ai5.live_data.tick import LiveTick


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _tick(*, timestamp: float = 1_700_000_000.0) -> LiveTick:
    return LiveTick(
        timestamp=timestamp,
        symbol="MNQ",
        last_price=20100.0,
        bid=20099.75,
        ask=20100.0,
        volume=1.0,
    )


def test_initial_status_is_disconnected() -> None:
    monitor = FeedHealthMonitor(clock=FakeClock())
    snap = monitor.snapshot()
    assert snap.feed_status is FeedStatus.DISCONNECTED
    assert snap.connection_quality is ConnectionQuality.UNKNOWN
    assert snap.last_tick_age_ms is None
    assert snap.tick_delay_ms is None
    assert snap.average_tick_rate == 0.0
    assert snap.peak_tick_rate == 0.0


def test_record_tick_becomes_healthy_with_delay_and_rates() -> None:
    mono = FakeClock(10.0)
    wall = FakeClock(1_700_000_000.5)
    monitor = FeedHealthMonitor(clock=mono, wall_clock=wall)
    previous = monitor.record_tick(_tick(timestamp=1_700_000_000.0))
    assert previous is FeedStatus.DISCONNECTED
    assert monitor.feed_status is FeedStatus.HEALTHY

    snap = monitor.snapshot()
    assert snap.feed_status is FeedStatus.HEALTHY
    assert snap.connection_quality is ConnectionQuality.GOOD
    assert snap.last_tick_age_ms == 0.0
    assert snap.tick_delay_ms == 500.0
    assert snap.average_tick_rate == 0.0  # elapsed still 0 at same mono time
    mono.now = 11.0
    snap = monitor.snapshot()
    assert snap.average_tick_rate == pytest.approx(1.0)
    assert snap.peak_tick_rate == pytest.approx(1.0)


def test_stall_then_disconnect_transitions() -> None:
    clock = FakeClock(0.0)
    monitor = FeedHealthMonitor(
        stall_seconds=2.0,
        disconnect_seconds=5.0,
        clock=clock,
        wall_clock=FakeClock(1_700_000_000.0),
    )
    monitor.record_tick(_tick())

    clock.now = 2.5
    previous = monitor.evaluate()
    assert previous is FeedStatus.HEALTHY
    assert monitor.feed_status is FeedStatus.STALE
    assert monitor.snapshot().connection_quality is ConnectionQuality.POOR

    clock.now = 5.5
    previous = monitor.evaluate()
    assert previous is FeedStatus.STALE
    assert monitor.feed_status is FeedStatus.DISCONNECTED


def test_peak_rate_tracks_burst() -> None:
    clock = FakeClock(0.0)
    monitor = FeedHealthMonitor(clock=clock, wall_clock=FakeClock(1_700_000_000.0))
    for _ in range(5):
        monitor.record_tick(_tick())
    assert monitor.snapshot().peak_tick_rate == pytest.approx(5.0)

    clock.now = 2.0
    monitor.record_tick(_tick())
    # Peak retains historical max even after window empties prior bursts.
    assert monitor.snapshot().peak_tick_rate == pytest.approx(5.0)


def test_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="stall_seconds"):
        FeedHealthMonitor(stall_seconds=0)
    with pytest.raises(ValueError, match="disconnect_seconds must be"):
        FeedHealthMonitor(stall_seconds=5.0, disconnect_seconds=2.0)
