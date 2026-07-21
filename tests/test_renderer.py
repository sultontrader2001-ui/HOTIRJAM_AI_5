"""Tests for DashboardRenderer."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import (
    ConnectionQuality,
    ConnectionStatus,
    DashboardState,
    DecisionAssessmentView,
    DecisionEvaluationView,
    DecisionFoundationView,
    DecisionIntentView,
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
    TradeDecisionView,
)
from hotirjam_ai5.dashboard.renderer import DashboardRenderer


def test_render_includes_required_sections_and_title() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "HOTIRJAM AI 5" in text
    assert "SYSTEM" in text
    assert "LIVE MARKET" in text
    assert "FEED HEALTH" in text
    assert "DOM HEALTH" in text
    assert "PHYSICS" in text
    assert "STATISTICS" in text
    assert "MARKET ANALYSIS" in text
    assert "CONTEXT" in text
    assert "DECISION FOUNDATION" in text
    assert "DECISION INTENT" in text
    assert "DECISION EVALUATION" in text
    assert "DECISION ASSESSMENT" in text
    assert "TRADE DECISION" in text
    assert "LOG" in text
    assert "State       :" in text
    assert "Transition  :" in text
    assert "Behavior    :" in text
    assert "Ready :" in text
    assert "Intent :" in text
    assert "Allowed :" in text
    assert "Decision:" in text


def test_render_shows_placeholder_not_fake_prices() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "Price  : —" in text
    assert "TickAge : —" in text
    assert "Velocity : —" in text
    assert "Accel    : —" in text
    assert "State       : UNKNOWN" in text
    assert "Transition  : NONE" in text
    assert "Behavior    : UNKNOWN" in text
    assert "Insufficient market context." in text
    assert "Ready : NO" in text
    assert "Waiting for market context." in text
    assert "Intent : WAIT" in text
    assert "Reason : Observation layer is not ready." in text
    assert "Next   : No further processing." in text
    assert "Status  : IDLE" in text
    assert "Allowed : NO" in text
    assert "Reason  : Evaluation not started." in text
    assert "Next    : Continue Observation" in text
    assert "State : REVIEW" in text
    assert "Reason: Evaluation complete, awaiting final decision." in text
    assert "Next  : Decision Assessment Engine" in text
    assert "Decision: NO_TRADE" in text
    assert "Reason  : Decision assessment still under review." in text
    assert "Next    : Execution Engine" in text
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
            last_price=28762.25,
            bid=28761.50,
            ask=28762.25,
            volume=4.0,
        ),
        feed_health=FeedHealthView(
            feed_status=FeedStatus.HEALTHY,
            connection_quality=ConnectionQuality.GOOD,
            last_tick_age_ms=14.0,
            tick_delay_ms=45.0,
            average_tick_rate=37.0,
            peak_tick_rate=40.0,
        ),
        dom=DomView(
            best_bid_size=11,
            best_ask_size=9,
            total_bid_size=80,
            total_ask_size=70,
            depth_levels=10,
            update_rate=1470.0,
            status="OK",
        ),
        dom_health=DomHealthView(
            feed_status=FeedStatus.HEALTHY,
            connection_quality=ConnectionQuality.GOOD,
            last_update_age_ms=0.0,
            update_rate=1470.0,
            peak_update_rate=1500.0,
        ),
        physics=PhysicsView(
            spread=0.75,
            mid_price=28761.875,
            tick_velocity=7.09,
            tick_acceleration=32.01,
        ),
        market_state=MarketStateView(
            state="VOLATILE",
            reason="Rapid velocity change",
        ),
        market_transition=MarketTransitionView(
            current_state="VOLATILE",
            previous_state="ACTIVE",
            transition="NONE",
            changed=False,
            duration_seconds=18.0,
            reason="Market state remains VOLATILE",
        ),
        market_behavior=MarketBehaviorView(
            behavior="UNSTABLE",
            reason="Volatile market condition",
        ),
        market_context=MarketContextView(
            summary="Volatile market with unstable behavior.",
            state="VOLATILE",
            behavior="UNSTABLE",
            transition="NONE",
        ),
        decision_foundation=DecisionFoundationView(
            ready=True,
            summary="Observation layer complete.",
            blocking_reason="",
        ),
        decision_intent=DecisionIntentView(
            intent="OBSERVE",
            reason="Observation stable.",
            next_step="Continue monitoring.",
        ),
        decision_evaluation=DecisionEvaluationView(
            status="EVALUATING",
            evaluation_allowed=True,
            reason="Evaluation initiated.",
            next_stage="Decision Assessment Engine",
        ),
        decision_assessment=DecisionAssessmentView(
            assessment_state="READY",
            assessment_ready=True,
            reason="Evaluation completed successfully.",
            next_stage="Trade Decision Engine",
        ),
        trade_decision=TradeDecisionView(
            decision="NO_TRADE",
            reason="Trading policy not yet authorized.",
            next_action="Execution Engine",
        ),
        statistics=StatisticsView(
            tick_count=120,
            tick_rate=37.0,
            running_time_seconds=65,
        ),
        events=("Connected", "DOM connected"),
    )
    text = DashboardRenderer().render(state)
    assert "Status : RUNNING" in text
    assert "Conn   : CONNECTED" in text
    assert "Symbol : MNQ" in text
    assert "Price  : 28762.25" in text
    assert "Spread : 0.75" in text
    assert "Healthy" in text
    assert "TickAge : 14 ms" in text
    assert "Rate    : 37/s" in text
    assert "DOMAge  : 0 ms" in text
    assert "Rate    : 1470/s" in text
    assert "Velocity : 7.09" in text
    assert "Accel    : 32.01" in text
    assert "Tick Rate : 37/s" in text
    assert "MARKET ANALYSIS" in text
    assert "State       : VOLATILE" in text
    assert "Transition  : NONE" in text
    assert "Behavior    : UNSTABLE" in text
    assert "CONTEXT" in text
    assert "Volatile market with unstable behavior." in text
    assert "Ready : YES" in text
    assert "Observation layer complete." in text
    assert "DECISION INTENT" in text
    assert "Intent : OBSERVE" in text
    assert "Reason : Observation stable." in text
    assert "Next   : Continue monitoring." in text
    assert "DECISION EVALUATION" in text
    assert "Status  : EVALUATING" in text
    assert "Allowed : YES" in text
    assert "Reason  : Evaluation initiated." in text
    assert "Next    : Decision Assessment Engine" in text
    assert "DECISION ASSESSMENT" in text
    assert "State : READY" in text
    assert "Reason: Evaluation completed successfully." in text
    assert "Next  : Trade Decision Engine" in text
    assert "TRADE DECISION" in text
    assert "Decision: NO_TRADE" in text
    assert "Reason  : Trading policy not yet authorized." in text
    assert "Next    : Execution Engine" in text
    assert "• DOM connected" in text


def test_empty_log_shows_none() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "• (none)" in text


def test_two_column_headers_align() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "SYSTEM" in text and "LIVE MARKET" in text
    assert "FEED HEALTH" in text and "DOM HEALTH" in text
    assert "PHYSICS" in text and "STATISTICS" in text
