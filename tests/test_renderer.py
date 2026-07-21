"""Tests for DashboardRenderer."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import (
    ConnectionQuality,
    ConnectionStatus,
    DashboardState,
    DecisionFoundationView,
    DomHealthView,
    DomView,
    EngineStatus,
    FeedHealthView,
    FeedStatus,
    LiveMarketView,
    MarketBehaviorView,
    MarketContextView,
    MarketStateView,
    MarketTransitionView,
    MarketStatus,
    PhysicsView,
    StatisticsView,
    SystemView,
)
from hotirjam_ai5.dashboard.renderer import DashboardRenderer


def test_render_includes_required_sections_and_title() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "HOTIRJAM AI 5" in text
    assert "SYSTEM" in text
    assert "LIVE MARKET" in text
    assert "FEED HEALTH" in text
    assert "DOM" in text
    assert "DOM HEALTH" in text
    assert "PHYSICS" in text
    assert "MARKET STATE" in text
    assert "MARKET TRANSITION" in text
    assert "MARKET BEHAVIOR" in text
    assert "MARKET CONTEXT" in text
    assert "DECISION FOUNDATION" in text
    assert "STATISTICS" in text
    assert "LOG" in text
    assert "- Best Bid Size:" in text
    assert "- Tick Velocity:" in text
    assert "- Tick Acceleration:" in text
    assert "- State:" in text
    assert "- Reason:" in text
    assert "- Transition:" in text
    assert "- Changed:" in text
    assert "- Behavior:" in text
    assert "- Summary:" in text
    assert "- Ready:" in text


def test_render_shows_placeholder_not_fake_prices() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "Last Price: —" in text
    assert "Last Tick Age: —" in text
    assert "Best Bid Size: —" in text
    assert "Tick Velocity: —" in text
    assert "Tick Acceleration: —" in text
    assert "State: UNKNOWN" in text
    assert "Transition: NONE" in text
    assert "Changed: NO" in text
    assert "Behavior: UNKNOWN" in text
    assert "Summary: Insufficient market context." in text
    assert "Ready: NO" in text
    assert "Reason: Waiting for market context." in text
    assert "Tick Count: 0" in text


def test_render_with_real_market_and_health_values() -> None:
    state = DashboardState(
        system=SystemView(
            engine_status=EngineStatus.RUNNING,
            connection_status=ConnectionStatus.CONNECTED,
            market_status=MarketStatus.OPEN,
        ),
        market=LiveMarketView(
            symbol="MNQ",
            last_price=20100.5,
            bid=20100.25,
            ask=20100.5,
            volume=4.0,
        ),
        feed_health=FeedHealthView(
            feed_status=FeedStatus.HEALTHY,
            connection_quality=ConnectionQuality.GOOD,
            last_tick_age_ms=12.0,
            tick_delay_ms=45.0,
            average_tick_rate=8.5,
            peak_tick_rate=22.0,
        ),
        dom=DomView(
            best_bid_size=11,
            best_ask_size=9,
            total_bid_size=80,
            total_ask_size=70,
            depth_levels=10,
            update_rate=15.0,
            status="OK",
        ),
        dom_health=DomHealthView(
            feed_status=FeedStatus.HEALTHY,
            connection_quality=ConnectionQuality.GOOD,
            last_update_age_ms=8.0,
            update_rate=15.0,
            peak_update_rate=40.0,
        ),
        physics=PhysicsView(
            spread=0.25,
            mid_price=20100.375,
            tick_velocity=1.5,
            tick_acceleration=-0.25,
        ),
        market_state=MarketStateView(
            state="ACTIVE",
            reason="Tick activity increasing",
        ),
        market_transition=MarketTransitionView(
            current_state="ACTIVE",
            previous_state="QUIET",
            transition="QUIET → ACTIVE",
            changed=True,
            duration_seconds=18.0,
            reason="Market state changed from QUIET to ACTIVE",
        ),
        market_behavior=MarketBehaviorView(
            behavior="ACCELERATING",
            reason="Tick velocity increasing",
        ),
        market_context=MarketContextView(
            summary="Trending market with accelerating behavior.",
            state="ACTIVE",
            behavior="ACCELERATING",
            transition="QUIET → ACTIVE",
        ),
        decision_foundation=DecisionFoundationView(
            ready=True,
            summary="Observation layer complete.",
            blocking_reason="",
        ),
        statistics=StatisticsView(
            tick_count=120,
            tick_rate=12.5,
            running_time_seconds=65,
        ),
        events=("Connected", "DOM connected"),
    )
    text = DashboardRenderer().render(state)
    assert "PHYSICS" in text
    assert "MARKET STATE" in text
    assert "MARKET BEHAVIOR" in text
    assert "MARKET CONTEXT" in text
    assert "DECISION FOUNDATION" in text
    assert "State: ACTIVE" in text
    assert "Reason: Tick activity increasing" in text
    assert "Current: ACTIVE" in text
    assert "Previous: QUIET" in text
    assert "Transition: QUIET → ACTIVE" in text
    assert "Changed: YES" in text
    assert "Duration: 18 s" in text
    assert "Behavior: ACCELERATING" in text
    assert "Reason: Tick velocity increasing" in text
    assert "Summary: Trending market with accelerating behavior." in text
    assert "Ready: YES" in text
    assert "Summary: Observation layer complete." in text
    assert "Spread: 0.25" in text
    assert "Mid Price: 20100.38" in text
    assert "Tick Velocity: 1.5000" in text
    assert "Tick Acceleration: -0.2500" in text
    assert "• DOM connected" in text


def test_empty_log_shows_none() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "• (none)" in text
