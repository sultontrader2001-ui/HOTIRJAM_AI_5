"""Tests for Professional Dual-Column Dashboard renderer (Sprint 48)."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import (
    AccountStatusView,
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
    LastSignalView,
    LiveMarketView,
    LiquidityView,
    MarketBehaviorView,
    MarketContextView,
    MarketStateView,
    MarketTransitionView,
    MarketStatus,
    MemoryBandView,
    MemoryPanelView,
    PerformanceView,
    PeriodStatsView,
    PhysicsView,
    SignalHistoryRowView,
    StatisticsView,
    SystemPanelView,
    SystemView,
    TradeDecisionView,
)
from hotirjam_ai5.dashboard.renderer import (
    DUAL_COLUMN_MIN_WIDTH,
    DashboardRenderer,
    LABEL_WIDTH,
    MISSING,
)


def _sample_state() -> DashboardState:
    return DashboardState(
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
        dom_health=DomHealthView(
            feed_status=FeedStatus.HEALTHY,
            update_rate=1470.0,
        ),
        physics=PhysicsView(
            spread=0.75,
            mid_price=28761.875,
            tick_velocity=7.09,
            tick_acceleration=32.01,
        ),
        market_state=MarketStateView(state="VOLATILE"),
        market_behavior=MarketBehaviorView(behavior="UNSTABLE"),
        decision_assessment=DecisionAssessmentView(assessment_state="READY"),
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
            memory_influence_pct=80.0,
            memory_agreement=96.0,
            memory_persistence=88.0,
            explanation=DecisionExplanationView(),
            explainability=DecisionExplainabilityView(headline="BUY selected because"),
        ),
        statistics=StatisticsView(tick_rate=37.0, running_time_seconds=65),
        performance=PerformanceView(),
        today_stats=PeriodStatsView(
            signals=4,
            buy_signals=3,
            sell_signals=1,
            wins=2,
            losses=1,
            win_rate=66.7,
            average_mfe=1.25,
            average_mae=-0.50,
            average_rr=2.50,
            profit_factor=1.80,
        ),
        lifetime_stats=PeriodStatsView(
            signals=4,
            wins=2,
            losses=1,
            win_rate=66.7,
            profit_factor=1.80,
            memory_accuracy=100.0,
            net_points=2.5,
            largest_win=1.25,
            largest_loss=-0.5,
        ),
        account_status=AccountStatusView(
            starting_balance=50_000.0,
            current_balance=50_120.0,
            current_equity=50_120.0,
            today_pnl=40.0,
            weekly_pnl=80.0,
            monthly_pnl=120.0,
            lifetime_pnl=120.0,
            profit_target=3_000.0,
            progress_pct=4.0,
            remaining_profit=2_880.0,
            risk_status="SAFE",
            win_rate=60.0,
            profit_factor=1.5,
        ),
        signal_history=(
            SignalHistoryRowView(
                index=1,
                time_label="10:30:00",
                direction="BUY",
                entry=28760.0,
                exit=28761.25,
                result="WIN",
                points=1.25,
                duration_label="5m 00s",
                memory_effect="HELPED",
            ),
        ),
        liquidity=LiquidityView(shift="BUY", imbalance="BUY"),
        display_clock=DisplayClockView(
            new_york="2026-07-21 10:37:15 EDT",
            tashkent="2026-07-21 19:37:15 UZT",
        ),
        memory_panel=MemoryPanelView(
            fast=MemoryBandView(
                name="FAST",
                direction="BUY",
                strength=80.0,
                confidence=90.0,
                persistence=95.0,
            ),
            medium=MemoryBandView(
                name="MEDIUM",
                direction="BUY",
                strength=75.0,
                confidence=88.0,
                persistence=90.0,
            ),
            slow=MemoryBandView(
                name="SLOW",
                direction="BUY",
                strength=70.0,
                confidence=85.0,
                persistence=88.0,
            ),
            consensus_direction="BUY",
            consensus_agreement=96.0,
            consensus_confidence=88.0,
            consensus_status="ALIGNED",
        ),
        last_signal=LastSignalView(),
        system_panel=SystemPanelView(
            memory_records=400,
            memory_usage_pct=19.5,
            decision_count=120,
            append_rate=12.5,
            version="0.1.0",
            git_commit="abc1234",
        ),
        decision_foundation=DecisionFoundationView(ready=True),
        decision_intent=DecisionIntentView(),
        decision_evaluation=DecisionEvaluationView(),
        market_context=MarketContextView(),
        market_transition=MarketTransitionView(),
        dom=DomView(),
    )


def test_render_includes_professional_sections() -> None:
    text = DashboardRenderer().render(DashboardState(), width=100)
    assert "HOTIRJAM AI 5 LIVE" in text
    assert "MARKET" in text
    assert "AI STATUS" in text
    assert "TRADE DECISION" in text
    assert "MEMORY" in text
    assert "ACCOUNT STATUS" in text
    assert "TODAY" in text
    assert "LIFETIME" in text
    assert "SIGNAL HISTORY" in text
    assert "SYSTEM" in text
    assert "┌" in text and "┐" in text
    assert "DECISION EXPLANATION" not in text


def test_dual_column_mode_at_160() -> None:
    text = DashboardRenderer().render(_sample_state(), width=DUAL_COLUMN_MIN_WIDTH)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    # Two boxed panels should appear on the same row (MARKET left, TODAY right).
    dual_rows = [ln for ln in lines if ln.count("┌") >= 2 or (ln.count("│") >= 4 and "MARKET" not in ln)]
    assert any(ln.count("┌") == 2 for ln in lines) or any(
        "TODAY" in ln and "MARKET" in text.split("TODAY")[0]
        for ln in lines
    )
    # Side-by-side: a line containing two panel top borders
    assert any(ln.count("┌") == 2 for ln in lines)
    assert "Weekly P/L" in text
    assert "Monthly P/L" in text
    assert "Memory Usage" in text
    assert "Append Rate" in text
    assert ">>> BUY_INTERNAL <<<" in text


def test_single_column_fallback_below_160() -> None:
    text = DashboardRenderer().render(_sample_state(), width=100)
    lines = text.splitlines()
    # Single column: only one panel top border per row
    for ln in lines:
        assert ln.count("┌") <= 1
    assert "MARKET" in text
    assert "TODAY" in text
    # Order: MARKET before TODAY in single-column stack
    assert text.index("MARKET") < text.index("TODAY")
    assert text.index("TODAY") < text.index("LIFETIME")
    assert text.index("ACCOUNT STATUS") < text.index("SYSTEM")


def test_default_hides_verbose_pipeline_details() -> None:
    text = DashboardRenderer().render(DashboardState(), width=100)
    assert "DECISION FOUNDATION" not in text
    assert "VERBOSE" not in text
    assert "LOG" not in text


def test_verbose_shows_pipeline_details() -> None:
    text = DashboardRenderer(verbose=True).render(DashboardState(), width=100)
    assert "VERBOSE" in text
    assert "DECISION EXPLANATION" in text
    assert "LOG" in text


def test_missing_values_use_double_dash() -> None:
    text = DashboardRenderer().render(DashboardState(), width=100)
    assert MISSING == "--"
    assert MISSING in text


def test_buy_internal_is_emphasized() -> None:
    state = DashboardState(trade_decision=TradeDecisionView(decision="BUY_INTERNAL"))
    text = DashboardRenderer().render(state, width=100)
    assert ">>> BUY_INTERNAL <<<" in text


def test_sell_internal_is_emphasized() -> None:
    state = DashboardState(trade_decision=TradeDecisionView(decision="SELL_INTERNAL"))
    text = DashboardRenderer().render(state, width=100)
    assert ">>> SELL_INTERNAL <<<" in text


def test_values_right_aligned_in_panel() -> None:
    text = DashboardRenderer().render(_sample_state(), width=100)
    # Find a MARKET content row with Symbol / MNQ
    rows = [ln for ln in text.splitlines() if "Symbol" in ln and "MNQ" in ln]
    assert rows
    row = rows[0]
    assert row.index("Symbol") < row.rindex("MNQ")
    assert LABEL_WIDTH == 18


def test_signal_history_columns() -> None:
    text = DashboardRenderer().render(_sample_state(), width=100)
    assert "SIGNAL HISTORY" in text
    assert "Time" in text
    assert "Side" in text
    assert "Result" in text
    assert "Points" in text
    assert "Duration" in text
    assert "Memory" in text
    assert "HELPED" in text
    assert "1.25" in text


def test_render_with_populated_professional_layout() -> None:
    text = DashboardRenderer().render(_sample_state(), width=100)
    assert "MNQ" in text
    assert "28762.25" in text
    assert "37/s" in text
    assert "1470/s" in text
    assert "80.0%" in text
    assert "96.0%" in text
    assert "Fast Band" in text
    assert "ALIGNED" in text
    assert "+1.25" in text
    assert "-0.50" in text
    assert "1.80" in text
    assert "abc1234" in text
    assert "$50,000.00" in text
    assert "Weekly P/L" in text

    verbose = DashboardRenderer(verbose=True).render(_sample_state(), width=100)
    assert "DECISION EXPLANATION" in verbose
    assert "BUY selected because" in verbose
