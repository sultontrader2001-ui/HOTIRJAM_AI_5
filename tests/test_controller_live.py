"""Tests for live-tick dashboard controller behavior."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.dashboard.models import ConnectionStatus, EngineStatus, MarketStatus
from hotirjam_ai5.live_data.tick import LiveTick


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _tick(*, price: float = 20100.0, symbol: str = "MNQ") -> LiveTick:
    return LiveTick(
        timestamp=1_700_000_000.0,
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


def test_connected_only_after_first_valid_tick() -> None:
    controller = DashboardController()
    controller.start()
    controller.on_tick(_tick(price=20100.5))
    state = controller.snapshot()
    assert state.system.connection_status is ConnectionStatus.CONNECTED
    assert state.system.market_status is MarketStatus.OPEN
    assert state.market.last_price == 20100.5
    assert state.market.bid == 20100.25
    assert state.market.ask == 20100.5
    assert state.market.volume == 3.0
    assert state.statistics.tick_count == 1
    assert "Connection established" in state.events
    assert any(event.startswith("Tick received") for event in state.events)


def test_connection_lost_after_stale_timeout() -> None:
    clock = FakeClock(0.0)
    controller = DashboardController(stale_seconds=2.0, clock=clock)
    controller.start()
    controller.on_tick(_tick())
    assert controller.snapshot().system.connection_status is ConnectionStatus.CONNECTED

    clock.now = 2.5
    controller.check_connection_health()
    state = controller.snapshot()
    assert state.system.connection_status is ConnectionStatus.DISCONNECTED
    assert state.system.market_status is MarketStatus.WAITING
    assert "Connection lost" in state.events


def test_reconnect_logs_connection_established_again() -> None:
    clock = FakeClock(0.0)
    controller = DashboardController(stale_seconds=1.0, clock=clock)
    controller.start()
    controller.on_tick(_tick(price=100.0))
    clock.now = 5.0
    controller.check_connection_health()
    controller.on_tick(_tick(price=101.0))
    events = controller.snapshot().events
    assert events.count("Connection established") == 2
    assert controller.snapshot().market.last_price == 101.0


def test_reject_non_positive_stale_seconds() -> None:
    with pytest.raises(ValueError, match="stale_seconds"):
        DashboardController(stale_seconds=0)
