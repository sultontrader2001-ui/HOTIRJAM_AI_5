"""Tests for DOM controller integration."""

from __future__ import annotations

from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.dashboard.models import FeedStatus
from hotirjam_ai5.live_data.dom import DomSnapshot


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _dom() -> DomSnapshot:
    return DomSnapshot(
        timestamp_utc="2026-07-21T00:00:00.0000000Z",
        instrument="MNQ",
        depth_levels=10,
        best_bid_size=5,
        best_ask_size=7,
        total_bid_size=40,
        total_ask_size=35,
        status="OK",
    )


def test_on_dom_updates_view_and_logs_connected() -> None:
    controller = DashboardController()
    controller.start()
    controller.on_dom(_dom())
    state = controller.snapshot()
    assert state.dom.best_bid_size == 5
    assert state.dom.best_ask_size == 7
    assert state.dom.total_bid_size == 40
    assert state.dom.total_ask_size == 35
    assert state.dom.depth_levels == 10
    assert state.dom_health.feed_status is FeedStatus.HEALTHY
    assert "DOM connected" in state.events


def test_dom_stalled_resumed_and_lost() -> None:
    clock = FakeClock(0.0)
    controller = DashboardController(
        stall_seconds=2.0,
        stale_seconds=5.0,
        clock=clock,
        wall_clock=FakeClock(1_700_000_000.0),
    )
    controller.start()
    controller.on_dom(_dom())
    clock.now = 2.5
    controller.check_connection_health()
    assert controller.snapshot().dom_health.feed_status is FeedStatus.STALE
    assert "DOM stalled" in controller.snapshot().events

    controller.on_dom(_dom())
    assert "DOM resumed" in controller.snapshot().events

    clock.now = 10.0
    controller.check_connection_health()
    assert controller.snapshot().dom_health.feed_status is FeedStatus.DISCONNECTED
    assert "DOM connection lost" in controller.snapshot().events
