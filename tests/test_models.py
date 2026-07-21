"""Tests for dashboard view models."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    DashboardState,
    EngineStatus,
    LiveMarketView,
    MarketStatus,
    StatisticsView,
    SystemView,
)


def test_live_market_spread_when_both_sides_present() -> None:
    market = LiveMarketView(bid=100.0, ask=100.25)
    assert market.spread == 0.25


def test_live_market_spread_missing_when_incomplete() -> None:
    assert LiveMarketView(bid=100.0).spread is None
    assert LiveMarketView(ask=100.25).spread is None
    assert LiveMarketView().spread is None


def test_default_state_has_no_fake_prices() -> None:
    state = DashboardState()
    assert state.system.engine_status is EngineStatus.STARTING
    assert state.system.connection_status is ConnectionStatus.DISCONNECTED
    assert state.system.market_status is MarketStatus.WAITING
    assert state.market.symbol == "MNQ"
    assert state.market.last_price is None
    assert state.market.bid is None
    assert state.market.ask is None
    assert state.market.volume is None
    assert state.market_state.state == "UNKNOWN"
    assert state.market_transition.transition == "NONE"
    assert state.market_transition.changed is False
    assert state.market_behavior.behavior == "UNKNOWN"
    assert state.market_context.summary == "Insufficient market context."
    assert state.decision_foundation.ready is False
    assert state.decision_intent.intent == "WAIT"
    assert state.decision_evaluation.status == "IDLE"
    assert state.decision_evaluation.evaluation_allowed is False
    assert state.decision_assessment.assessment_state == "REVIEW"
    assert state.decision_assessment.assessment_ready is False
    assert state.trade_decision.decision == "NO_TRADE"
    assert state.statistics == StatisticsView()
    assert state.events == ()


def test_system_view_custom_values() -> None:
    system = SystemView(
        engine_status=EngineStatus.RUNNING,
        connection_status=ConnectionStatus.CONNECTED,
        market_status=MarketStatus.OPEN,
    )
    assert system.engine_status is EngineStatus.RUNNING
    assert system.connection_status is ConnectionStatus.CONNECTED
    assert system.market_status is MarketStatus.OPEN
