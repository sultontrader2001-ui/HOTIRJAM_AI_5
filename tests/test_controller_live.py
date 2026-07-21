"""Tests for live-tick dashboard controller behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.dashboard.signal_log import SignalLogWriter
from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    EngineStatus,
    FeedStatus,
    MarketStatus,
)
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.trade_decision.models import (
    DecisionReadiness,
    SignalStability,
    TradeDecision,
    TradeDecisionSnapshot,
)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class BuyInternalDecisionEngine:
    """Test double proving dashboard-only activation handling."""

    def evaluate(self, *_args: object, **_kwargs: object) -> TradeDecisionSnapshot:
        return TradeDecisionSnapshot(
            timestamp=1_700_000_000.5,
            decision=TradeDecision.BUY_INTERNAL,
            reason="Decision Readiness is READY.",
            next_action="Execution Engine",
            buy_score=91,
            buy_confidence=93,
            signal_stability=SignalStability.STABLE,
            decision_readiness=DecisionReadiness.READY,
        )


class SellInternalDecisionEngine:
    """Test double proving SELL_INTERNAL logging and counting."""

    def evaluate(self, *_args: object, **_kwargs: object) -> TradeDecisionSnapshot:
        return TradeDecisionSnapshot(
            timestamp=1_700_000_001.25,
            decision=TradeDecision.SELL_INTERNAL,
            reason="SELL Decision Readiness is READY.",
            next_action="Execution Engine",
            sell_score=89,
            sell_confidence=91,
            sell_signal_stability=SignalStability.STABLE,
            sell_decision_readiness=DecisionReadiness.READY,
        )


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


def _read_signal_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def test_buy_internal_is_logged_to_file_not_dashboard(tmp_path: Path) -> None:
    log_path = tmp_path / "signals.log"
    controller = DashboardController(
        trade_decision=BuyInternalDecisionEngine(),  # type: ignore[arg-type]
        signal_log=SignalLogWriter(log_path),
    )
    controller.start()

    state = controller.snapshot()

    assert state.trade_decision.decision == "BUY_INTERNAL"
    assert state.statistics.buy_internal_count == 1
    assert state.statistics.sell_internal_count == 0
    assert state.statistics.no_trade_count == 0
    assert state.statistics.buy_internal_frequency == 100.0
    assert state.statistics.no_trade_frequency == 0.0
    # The dashboard event log stays clean: no signal debug lines on screen.
    assert not any("BUY_INTERNAL" in event for event in state.events)
    lines = _read_signal_lines(log_path)
    assert len(lines) == 1
    log = lines[0]
    assert log.startswith("BUY_INTERNAL timestamp=1700000000.500000")
    assert "score=91" in log
    assert "confidence=93" in log
    assert "state=UNKNOWN" in log
    assert "behavior=UNKNOWN" in log
    assert "physics=velocity:None,acceleration:None" in log
    assert "liquidity=shift:UNKNOWN,imbalance:UNKNOWN" in log


def test_sell_internal_is_logged_to_file_not_dashboard(tmp_path: Path) -> None:
    log_path = tmp_path / "signals.log"
    controller = DashboardController(
        trade_decision=SellInternalDecisionEngine(),  # type: ignore[arg-type]
        signal_log=SignalLogWriter(log_path),
    )
    controller.start()
    controller.on_tick(_tick(price=20155.5))

    state = controller.snapshot()

    assert state.trade_decision.decision == "SELL_INTERNAL"
    assert state.statistics.sell_internal_count == 1
    assert state.statistics.buy_internal_count == 0
    assert state.statistics.sell_internal_frequency == 100.0
    # The dashboard event log stays clean: no signal debug lines on screen.
    assert not any("SELL_INTERNAL" in event for event in state.events)
    lines = _read_signal_lines(log_path)
    assert any(line.startswith("SELL_INTERNAL ") for line in lines)
    log = next(line for line in lines if line.startswith("SELL_INTERNAL "))
    assert "timestamp=1700000001.250000" in log
    assert "price=20155.5" in log
    assert "score=89" in log
    assert "confidence=91" in log
    assert "state=" in log
    assert "behavior=" in log
    assert "physics=velocity:" in log
    assert "liquidity=shift:" in log
