"""Tests for live-tick dashboard controller behavior."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    EngineStatus,
    FeedStatus,
    MarketStatus,
)
from hotirjam_ai5.live_data.tick import LiveTick


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _tick(*, price: float = 20100.0, symbol: str = "MNQ", timestamp: float = 1_700_000_000.0) -> LiveTick:
    return LiveTick(
        timestamp=timestamp,
        symbol=symbol,
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=3.0,
    )


def test_start_is_connecting_not_connected() -> None:
    controller = DashboardController()
    controller.start()
    state = controller.snapshot()
    assert state.system.engine_status is EngineStatus.RUNNING
    assert state.system.connection_status is ConnectionStatus.CONNECTING
    assert state.system.market_status is MarketStatus.WAITING
    assert state.market.last_price is None
    assert state.feed_health.feed_status is FeedStatus.DISCONNECTED
    assert state.events == ()


def test_connected_only_after_first_valid_tick() -> None:
    wall = FakeClock(1_700_000_000.2)
    controller = DashboardController(wall_clock=wall)
    controller.start()
    controller.on_tick(_tick(price=20100.5))
    state = controller.snapshot()
    assert state.system.connection_status is ConnectionStatus.CONNECTED
    assert state.system.market_status is MarketStatus.OPEN
    assert state.feed_health.feed_status is FeedStatus.HEALTHY
    assert state.market.last_price == 20100.5
    assert state.statistics.tick_count == 1
    assert state.events == ("Connected",)
    assert state.feed_health.tick_delay_ms == pytest.approx(200.0)


def test_feed_stalled_then_resumed_then_connection_lost() -> None:
    clock = FakeClock(0.0)
    controller = DashboardController(
        stall_seconds=2.0,
        stale_seconds=5.0,
        clock=clock,
        wall_clock=FakeClock(1_700_000_000.0),
    )
    controller.start()
    controller.on_tick(_tick())
    assert controller.snapshot().events == ("Connected",)

    clock.now = 2.5
    controller.check_connection_health()
    state = controller.snapshot()
    assert state.feed_health.feed_status is FeedStatus.STALE
    assert state.system.connection_status is ConnectionStatus.CONNECTED
    assert "Feed stalled" in state.events

    controller.on_tick(_tick(price=20101.0))
    state = controller.snapshot()
    assert state.feed_health.feed_status is FeedStatus.HEALTHY
    assert "Feed resumed" in state.events

    clock.now = 10.0
    controller.check_connection_health()
    state = controller.snapshot()
    assert state.feed_health.feed_status is FeedStatus.DISCONNECTED
    assert state.system.connection_status is ConnectionStatus.DISCONNECTED
    assert "Connection lost" in state.events


def test_reconnect_logs_connected_again() -> None:
    clock = FakeClock(0.0)
    controller = DashboardController(
        stall_seconds=1.0,
        stale_seconds=2.0,
        clock=clock,
        wall_clock=FakeClock(1_700_000_000.0),
    )
    controller.start()
    controller.on_tick(_tick(price=100.0))
    clock.now = 5.0
    controller.check_connection_health()
    controller.on_tick(_tick(price=101.0))
    events = controller.snapshot().events
    assert events.count("Connected") == 2
    assert "Tick received" not in events
    assert controller.snapshot().market.last_price == 101.0


def test_reject_non_positive_stale_seconds() -> None:
    with pytest.raises(ValueError, match="stale_seconds"):
        DashboardController(stale_seconds=0)
