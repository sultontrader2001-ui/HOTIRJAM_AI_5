"""Tests for DashboardRenderer (Live Dashboard v2)."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import (
    ConnectionQuality,
    ConnectionStatus,
    DashboardState,
    DecisionAssessmentView,
    DecisionEvaluationView,
    DecisionExplanationView,
    DecisionExplainabilityView,
    DecisionFoundationView,
    DecisionIntentView,
    DisplayClockView,
    DomHealthView,
    DomView,
    EngineStatus,
    FeedHealthView,
    FeedStatus,
    LiveMarketView,
    LiquidityView,
    MarketBehaviorView,
    MarketContextView,
    MarketStateView,
    MarketTransitionView,
    MarketStatus,
    PerformanceView,
    PhysicsView,
    StatisticsView,
    SystemView,
    TradeDecisionView,
)
from hotirjam_ai5.dashboard.renderer import DashboardRenderer, LABEL_WIDTH


def test_render_includes_live_v2_sections_and_title() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "HOTIRJAM AI 5 LIVE" in text
    assert "MARKET" in text
    assert "AI STATUS" in text
    assert "TRADE DECISION" in text
    assert "DECISION EXPLANATION" in text
    assert "PERFORMANCE" in text
    assert "SYSTEM" in text
    assert "NY Time" in text
    assert "UZ Time" in text
    assert "Decision Readiness" in text
    assert "Win Rate" in text
    assert "Last Result" in text
    assert "Tick Rate" in text
    assert "Connection" in text


def test_default_hides_verbose_pipeline_details() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "DECISION FOUNDATION" not in text
    assert "DECISION INTENT" not in text
    assert "DECISION EVALUATION" not in text
    assert "VERBOSE" not in text
    assert "Observation layer is not ready." not in text
    assert "Explanation" not in text
    assert "LOG" not in text
    assert "STATISTICS" not in text


def test_verbose_shows_pipeline_details() -> None:
    text = DashboardRenderer(verbose=True).render(DashboardState())
    assert "VERBOSE" in text
    assert "DECISION FOUNDATION" in text
    assert "DECISION INTENT" in text
    assert "DECISION EVALUATION" in text
    assert "DECISION ASSESSMENT" in text
    assert "Explanation" in text
    assert "LOG" in text
    assert "• (none)" in text
    assert "Intent" in text
    assert "Reason" in text
    assert "Next" in text


def test_render_shows_placeholder_not_fake_prices() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "Price             : —" in text or _row_contains(text, "Price", "—")
    assert "Decision : NO_TRADE" in text
    assert "BUY Score         : 0 / 100" in text or "BUY Score" in text
    assert "BUY Confidence" in text
    assert "SELL Score" in text
    assert "SELL Confidence" in text
    assert "Signal Stability" in text
    assert "Market State" in text
    assert "UNKNOWN" in text


def _row_contains(text: str, label: str, value: str) -> bool:
    return any(
        line.startswith(f"{label:<{LABEL_WIDTH}}: ") and value in line
        for line in text.splitlines()
    )


def test_buy_internal_is_emphasized() -> None:
    state = DashboardState(
        trade_decision=TradeDecisionView(decision="BUY_INTERNAL"),
    )
    text = DashboardRenderer().render(state)
    assert ">>>  BUY_INTERNAL  <<<" in text
    assert "Decision : NO_TRADE" not in text


def test_sell_internal_is_emphasized() -> None:
    state = DashboardState(
        trade_decision=TradeDecisionView(decision="SELL_INTERNAL"),
    )
    text = DashboardRenderer().render(state)
    assert ">>>  SELL_INTERNAL  <<<" in text


def test_no_trade_is_visible_but_less_dominant() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "Decision : NO_TRADE" in text
    assert ">>>  BUY_INTERNAL  <<<" not in text
    assert ">>>  SELL_INTERNAL  <<<" not in text


def test_column_labels_align() -> None:
    text = DashboardRenderer().render(DashboardState())
    labels = [
        "Symbol",
        "Price",
        "Market State",
        "BUY Score",
        "Win Rate",
        "Tick Rate",
    ]
    for label in labels:
        matches = [line for line in text.splitlines() if line.startswith(label)]
        assert matches, label
        assert matches[0].index(":") == LABEL_WIDTH


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
            decision="BUY_INTERNAL",
            buy_score=88,
            buy_confidence=92,
            sell_score=35,
            sell_confidence=40,
            signal_stability="STABLE",
            sell_signal_stability="UNSTABLE",
            decision_readiness="READY",
            sell_decision_readiness="NOT_READY",
            reason=(
                "BUY requirements are satisfied and Decision Readiness is READY. "
                "Awaiting release."
            ),
            next_action="Execution Engine",
            explanation=DecisionExplanationView(
                assessment="PASS",
                feed="PASS",
                market_state="PASS",
                behavior="PASS",
                physics="PASS",
                liquidity="PASS",
                signal_stability="PASS",
                readiness="PASS",
                summary=(
                    "BUY requirements are satisfied and Decision Readiness is READY. "
                    "Awaiting release."
                ),
            ),
            explainability=DecisionExplainabilityView(
                headline="BUY selected because",
                buy_lines=(
                    "Assessment    +20",
                    "Feed          +15",
                    "State         +15",
                    "Behavior      +15",
                    "Physics       +20",
                    "Liquidity     +15",
                ),
                buy_total=100,
                sell_lines=(
                    "Assessment    +20",
                    "Feed          +15",
                    "State          +0",
                    "Behavior       +0",
                    "Physics        +0",
                    "Liquidity      +0",
                ),
                sell_total=35,
                buy_detail_lines=(
                    "Physics",
                    "Velocity           +242.73 ✓",
                    "Acceleration       +18.52 ✓",
                    "Direction          BUY",
                    "Score              +20",
                    "Liquidity",
                    "Liquidity Shift    BUY",
                    "DOM Imbalance      BUY",
                    "Direction Confirmed YES",
                    "Score              +15",
                    "BUY",
                    "Assessment    +20",
                    "Feed          +15",
                    "State         +15",
                    "Behavior      +15",
                    "Physics       +20",
                    "Liquidity     +15",
                    "TOTAL         100",
                    "Reason",
                    "BUY confirmed by",
                    "Market State,",
                    "Behavior,",
                    "Physics,",
                    "Liquidity.",
                ),
                buy_reason=(
                    "BUY confirmed by\nMarket State,\nBehavior,\nPhysics,\nLiquidity."
                ),
                selection_lines=(
                    "Physics confirmed BUY",
                    "Liquidity confirmed BUY",
                    "BUY score 100",
                    "BUY confidence 92%",
                    "SELL score 35",
                ),
            ),
        ),
        statistics=StatisticsView(
            tick_count=120,
            tick_rate=37.0,
            running_time_seconds=65,
            buy_internal_count=3,
            sell_internal_count=1,
            no_trade_count=6,
            buy_internal_frequency=30.0,
            sell_internal_frequency=10.0,
            no_trade_frequency=60.0,
        ),
        performance=PerformanceView(
            buy_signals=3,
            sell_signals=1,
            success_count=2,
            failed_count=1,
            win_rate=66.7,
            average_points=1.25,
            last_result="SUCCESS",
            last_signal_decision="BUY_INTERNAL",
            last_signal_utc="2026-07-21 14:37:15",
            last_signal_new_york="2026-07-21 10:37:15 EDT",
            last_signal_tashkent="2026-07-21 19:37:15 UZT",
        ),
        liquidity=LiquidityView(shift="BUY", imbalance="BUY"),
        display_clock=DisplayClockView(
            new_york="2026-07-21 10:37:15 EDT",
            tashkent="2026-07-21 19:37:15 UZT",
        ),
        events=("Connected", "DOM connected"),
    )
    text = DashboardRenderer().render(state)
    assert "Symbol            : MNQ" in text
    assert "Price             : 28762.25" in text
    assert "Spread            : 0.75" in text
    assert "Market Status     : OPEN" in text
    assert "NY Time           : 2026-07-21 10:37:15 EDT" in text
    assert "UZ Time           : 2026-07-21 19:37:15 UZT" in text
    assert "Feed Health       : HEALTHY" in text
    assert "DOM Health        : HEALTHY" in text
    assert "Market State      : VOLATILE" in text
    assert "Behavior          : UNSTABLE" in text
    assert "v=7.09" in text and "a=32.01" in text
    assert "Liquidity         : BUY / BUY" in text
    assert "Assessment        : READY" in text
    assert "BUY READY / SELL NOT_READY" in text
    assert ">>>  BUY_INTERNAL  <<<" in text
    assert "DECISION EXPLANATION" in text
    assert "BUY selected because" in text
    assert "Physics confirmed BUY" in text
    assert "Velocity           +242.73 ✓" in text
    assert "Direction Confirmed YES" in text
    assert "BUY confirmed by" in text
    assert "TOTAL" in text
    assert "BUY Score         : 88 / 100" in text
    assert "BUY Confidence    : 92 %" in text
    assert "SELL Score        : 35 / 100" in text
    assert "SELL Confidence   : 40 %" in text
    assert "BUY STABLE / SELL UNSTABLE" in text
    assert "BUY Signals       : 3" in text
    assert "SELL Signals      : 1" in text
    assert "Win Rate          : 66.7%" in text
    assert "Last Result       : SUCCESS" in text
    assert "Tick Rate         : 37/s" in text
    assert "DOM Rate          : 1470/s" in text
    assert "Latency           : 45 ms" in text
    assert "Runtime           : 1m 05s" in text
    assert "Connection        : CONNECTED" in text
    # Default mode stays clean.
    assert "DECISION FOUNDATION" not in text
    assert "• DOM connected" not in text

    verbose = DashboardRenderer(verbose=True).render(state)
    assert "DECISION FOUNDATION" in verbose
    assert "Observation layer complete." in verbose
    assert "Intent" in verbose
    assert "• DOM connected" in verbose


def test_section_order_is_stable() -> None:
    text = DashboardRenderer().render(DashboardState())
    positions = {
        name: text.index(name)
        for name in ("MARKET", "AI STATUS", "TRADE DECISION", "PERFORMANCE", "SYSTEM")
    }
    assert (
        positions["MARKET"]
        < positions["AI STATUS"]
        < positions["TRADE DECISION"]
        < positions["PERFORMANCE"]
        < positions["SYSTEM"]
    )
