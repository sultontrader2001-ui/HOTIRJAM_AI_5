"""Tests for Professional Trading Dashboard v2 renderer (Sprint 45/46)."""

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
from hotirjam_ai5.dashboard.renderer import DashboardRenderer, LABEL_WIDTH, MISSING


def test_render_includes_professional_sections() -> None:
    text = DashboardRenderer().render(DashboardState())
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
    assert "PERFORMANCE" not in text
    assert "LAST SIGNAL" not in text
    assert "Fast Band" in text
    assert "Consensus" in text
    assert "Ticks/sec" in text
    assert "DOM updates/sec" in text
    assert "Memory Influence %" in text
    assert "Git Commit" in text
    # Explainability stays verbose-only.
    assert "DECISION EXPLANATION" not in text


def test_default_hides_verbose_pipeline_details() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "DECISION FOUNDATION" not in text
    assert "DECISION INTENT" not in text
    assert "DECISION EVALUATION" not in text
    assert "VERBOSE" not in text
    assert "LOG" not in text


def test_verbose_shows_pipeline_details() -> None:
    text = DashboardRenderer(verbose=True).render(DashboardState())
    assert "VERBOSE" in text
    assert "DECISION FOUNDATION" in text
    assert "DECISION EXPLANATION" in text
    assert "LOG" in text


def test_missing_values_use_double_dash() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert MISSING == "--"
    assert "Price" in text
    assert f"Price{' ' * (LABEL_WIDTH - 5)}: {MISSING}" in text or ": --" in text


def test_buy_internal_is_emphasized() -> None:
    state = DashboardState(
        trade_decision=TradeDecisionView(decision="BUY_INTERNAL"),
    )
    text = DashboardRenderer().render(state)
    assert ">>>  BUY_INTERNAL  <<<" in text


def test_sell_internal_is_emphasized() -> None:
    state = DashboardState(
        trade_decision=TradeDecisionView(decision="SELL_INTERNAL"),
    )
    text = DashboardRenderer().render(state)
    assert ">>>  SELL_INTERNAL  <<<" in text


def test_column_labels_align() -> None:
    text = DashboardRenderer().render(DashboardState())
    labels = [
        "Symbol",
        "Price",
        "Market State",
        "BUY Score",
        "Win Rate",
        "Ticks/sec",
        "Runtime",
    ]
    for label in labels:
        matches = [line for line in text.splitlines() if line.startswith(label)]
        assert matches, label
        assert matches[0].index(":") == LABEL_WIDTH


def test_render_with_populated_professional_layout() -> None:
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
        performance=PerformanceView(
            buy_signals=3,
            sell_signals=1,
            success_count=2,
            failed_count=1,
            win_rate=66.7,
            signals_today=4,
            average_mfe=1.25,
            average_mae=-0.50,
            average_rr=2.50,
            profit_factor=1.80,
            decision_accuracy=66.7,
        ),
        today_stats=PeriodStatsView(
            signals=4,
            buy_signals=3,
            sell_signals=1,
            no_trade=8,
            wins=2,
            losses=1,
            breakeven=1,
            win_rate=66.7,
            average_mfe=1.25,
            average_mae=-0.50,
            average_rr=2.50,
            profit_factor=1.80,
            memory_helped=1,
            memory_hurt=0,
            memory_no_effect=3,
        ),
        lifetime_stats=PeriodStatsView(
            signals=4,
            buy_signals=3,
            sell_signals=1,
            wins=2,
            losses=1,
            win_rate=66.7,
            profit_factor=1.80,
            memory_accuracy=100.0,
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
        last_signal=LastSignalView(
            direction="BUY",
            entry_time="2026-07-21 10:30:00 EDT",
            exit_time="2026-07-21 10:35:00 EDT",
            duration="5m 00s",
            result="SUCCESS",
            points=1.25,
            memory_effect="HELPED",
        ),
        system_panel=SystemPanelView(
            memory_records=400,
            decision_count=120,
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
    text = DashboardRenderer().render(state)
    assert "Symbol                : MNQ" in text
    assert "Price                 : 28762.25" in text
    assert "Ticks/sec             : 37/s" in text
    assert "DOM updates/sec       : 1470/s" in text
    assert "Memory Influence %    : 80.0%" in text
    assert "Memory Agreement %    : 96.0%" in text
    assert "Fast Band" in text
    assert "Direction             : BUY" in text
    assert "Status                : ALIGNED" in text
    assert "Average MFE           : +1.25" in text
    assert "Average MAE           : -0.50" in text
    assert "Profit Factor         : 1.80" in text
    assert "HELPED" in text
    assert "Git Commit            : abc1234" in text
    assert "TODAY" in text
    assert "LIFETIME" in text
    assert "SIGNAL HISTORY" in text
    assert "DECISION EXPLANATION" not in text

    verbose = DashboardRenderer(verbose=True).render(state)
    assert "DECISION EXPLANATION" in verbose
    assert "BUY selected because" in verbose
