"""Tests for Decision Explainability (Sprint 36) — real score exposure only."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.liquidity import LiquidityBias, LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision import (
    TradeDecision,
    apply_trade_decision_policy,
    build_decision_explainability,
)
from hotirjam_ai5.trade_decision.explainability import contributions_from_breakdown
from hotirjam_ai5.trade_decision.models import BuyScoreBreakdown


def _assessment(state: DecisionAssessmentState) -> DecisionAssessmentSnapshot:
    return DecisionAssessmentSnapshot(
        timestamp=100.0,
        assessment_state=state,
        assessment_ready=state is DecisionAssessmentState.READY,
        reason="Assessment workflow observation",
        next_stage="Assessment workflow next stage",
    )


def _context(
    *,
    state: str = "ACTIVE",
    behavior: str = "STABLE",
    feed_status: str = "HEALTHY",
    state_direction: str = "UP",
    behavior_direction: str = "BUY",
) -> MarketContextSnapshot:
    return MarketContextSnapshot(
        timestamp=100.0,
        state=state,
        state_reason="fixture",
        transition="NONE",
        transition_changed=False,
        transition_duration=12.0,
        behavior=behavior,
        behavior_reason="fixture",
        feed_status=feed_status,
        feed_quality="GOOD",
        dom_status="HEALTHY",
        dom_quality="GOOD",
        tick_rate=8.0,
        spread=0.25,
        summary="fixture",
        state_direction=state_direction,
        behavior_direction=behavior_direction,
    )


def _sell_context() -> MarketContextSnapshot:
    return _context(state_direction="DOWN", behavior_direction="SELL")


def _physics(
    *,
    velocity: float | None = 1.0,
    acceleration: float | None = 0.2,
) -> PhysicsSnapshot:
    return PhysicsSnapshot(
        spread=0.25,
        mid_price=20100.0,
        tick_velocity=velocity,
        tick_acceleration=acceleration,
        tick_count=50,
    )


def _liquidity(
    *,
    liquidity_shift: str = LiquidityBias.BUY.value,
    dom_imbalance: str = LiquidityBias.BUY.value,
) -> LiquiditySnapshot:
    return LiquiditySnapshot(
        timestamp=100.0,
        liquidity_shift=liquidity_shift,
        dom_imbalance=dom_imbalance,
        confidence=0.5,
    )


def test_buy_explanation_breakdown_matches_real_score() -> None:
    history = ((95, 95), (96, 96))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=1.0,
        signal_history=history,
    )
    assert snap.decision is TradeDecision.BUY_INTERNAL
    assert snap.explainability is not None
    expl = snap.explainability
    assert expl.headline == "BUY selected because"
    assert expl.buy_total == snap.buy_score == 100
    assert expl.sell_total == snap.sell_score
    labels = {line.label: line.points for line in expl.buy_contributions}
    assert labels == {
        "Assessment": 20,
        "Feed": 15,
        "Market State": 15,
        "Behavior": 15,
        "Physics": 20,
        "Liquidity": 15,
    }
    assert sum(labels.values()) == expl.buy_total
    assert "Physics confirmed BUY" in expl.selection_lines
    assert "Liquidity confirmed BUY" in expl.selection_lines
    assert "BUY score 100" in expl.selection_lines
    assert any(line.startswith("BUY confidence ") for line in expl.selection_lines)
    assert any(line.startswith("SELL score ") for line in expl.selection_lines)
    assert expl.checklist == ()


def test_sell_explanation_breakdown_matches_real_score() -> None:
    history = ((95, 95), (96, 96))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _sell_context(),
        _physics(velocity=-1.0, acceleration=-0.2),
        _liquidity(
            liquidity_shift=LiquidityBias.SELL.value,
            dom_imbalance=LiquidityBias.SELL.value,
        ),
        timestamp=2.0,
        sell_signal_history=history,
    )
    assert snap.decision is TradeDecision.SELL_INTERNAL
    expl = snap.explainability
    assert expl is not None
    assert expl.headline == "SELL selected because"
    assert expl.sell_total == snap.sell_score == 100
    sell_labels = {line.label: line.points for line in expl.sell_contributions}
    assert sell_labels["Physics"] == 20
    assert sell_labels["Liquidity"] == 15
    assert sum(sell_labels.values()) == expl.sell_total
    assert "Physics confirmed SELL" in expl.selection_lines
    assert "Liquidity confirmed SELL" in expl.selection_lines
    assert expl.buy_total == snap.buy_score
    assert expl.buy_total < expl.sell_total


def test_no_trade_explanation_shows_missing_requirements() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=3.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    expl = snap.explainability
    assert expl is not None
    assert expl.headline == "NO TRADE"
    assert expl.buy_total == snap.buy_score == 100
    assert expl.selection_lines == ()
    assert any("Stability not reached" in item for item in expl.checklist)
    assert any("BUY Decision Readiness" in item for item in expl.checklist)
    # Score/confidence already meet thresholds; checklist must reflect real values.
    assert any("BUY score ≥ 80" in item for item in expl.checklist)
    assert any("BUY confidence ≥ 85" in item for item in expl.checklist)


def test_no_trade_partial_score_checklist() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(state="QUIET", behavior="UNSTABLE"),
        None,
        None,
        timestamp=4.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    expl = snap.explainability
    assert expl is not None
    assert expl.buy_total == snap.buy_score
    assert expl.buy_total < 80
    assert any("BUY score < 80" in item for item in expl.checklist)
    assert any("Physics confirmed" in item and item.startswith("✗") for item in expl.checklist)
    assert any("Liquidity confirmed" in item and item.startswith("✗") for item in expl.checklist)


def test_contributions_never_reinvent_totals() -> None:
    breakdown = BuyScoreBreakdown(
        assessment=20,
        feed_health=15,
        market_state=0,
        behavior=0,
        physics=0,
        liquidity=0,
    )
    lines = contributions_from_breakdown(breakdown)
    assert sum(line.points for line in lines) == breakdown.total == 35


def test_explainability_rejects_mismatched_totals() -> None:
    from hotirjam_ai5.trade_decision.models import DecisionReadiness, SignalStability
    import pytest

    breakdown = BuyScoreBreakdown(20, 15, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="buy_breakdown.total"):
        build_decision_explainability(
            decision=TradeDecision.NO_TRADE,
            buy_breakdown=breakdown,
            sell_breakdown=breakdown,
            buy_score=99,
            buy_confidence=0,
            sell_score=35,
            sell_confidence=0,
            buy_stability=SignalStability.UNSTABLE,
            buy_readiness=DecisionReadiness.UNKNOWN,
            sell_readiness=DecisionReadiness.UNKNOWN,
            decision_explanation=None,
        )
