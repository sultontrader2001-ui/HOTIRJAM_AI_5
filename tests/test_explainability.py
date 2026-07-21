"""Tests for Decision Explainability v2 (Sprint 38) — real evidence only."""

from __future__ import annotations

import pytest

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
    capture_score_evidence,
)
from hotirjam_ai5.trade_decision.explainability import contributions_from_breakdown
from hotirjam_ai5.trade_decision.models import (
    BuyScoreBreakdown,
    DecisionReadiness,
    SignalStability,
)


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
    tick_delay_ms: float | None = 19.0,
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
        tick_delay_ms=tick_delay_ms,
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


def test_buy_explanation_shows_real_physics_and_liquidity() -> None:
    history = ((95, 95), (96, 96))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(velocity=242.73, acceleration=18.52),
        _liquidity(),
        timestamp=1.0,
        signal_history=history,
    )
    assert snap.decision is TradeDecision.BUY_INTERNAL
    expl = snap.explainability
    assert expl is not None
    assert expl.evidence is not None
    assert expl.evidence.tick_velocity == pytest.approx(242.73)
    assert expl.evidence.tick_acceleration == pytest.approx(18.52)
    detail = "\n".join(expl.buy_detail_lines)
    assert "Velocity           +242.73 ✓" in detail
    assert "Acceleration       +18.52 ✓" in detail
    assert "Direction          BUY" in detail
    assert "Score              +20" in detail
    assert "Liquidity Shift    BUY" in detail
    assert "DOM Imbalance      BUY" in detail
    assert "Direction Confirmed YES" in detail
    assert "Latency" in detail and "19 ms" in detail
    assert "BUY confirmed by" in expl.buy_reason
    assert "Physics" in expl.buy_reason
    assert "Assessment" not in expl.buy_reason
    assert expl.buy_total == 100


def test_sell_physics_fails_on_buy_side_detail() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(velocity=-1.81, acceleration=-19.42),
        _liquidity(liquidity_shift="BUY", dom_imbalance="SELL"),
        timestamp=2.0,
    )
    expl = snap.explainability
    assert expl is not None
    buy_detail = "\n".join(expl.buy_detail_lines)
    assert "Velocity           -1.81 ✗" in buy_detail
    assert "Acceleration       -19.42 ✗" in buy_detail
    assert "Direction          NONE" in buy_detail
    assert "Score              +0" in buy_detail
    assert "Direction Confirmed NO" in buy_detail


def test_market_state_and_behavior_show_direction() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(state="TRENDING", behavior="ACCELERATING"),
        _physics(),
        _liquidity(),
        timestamp=3.0,
    )
    expl = snap.explainability
    assert expl is not None
    detail = expl.buy_detail_lines
    assert "State" in detail
    assert "TRENDING" in detail
    assert "Direction" in detail
    assert "UP" in detail
    assert "Behavior" in detail
    assert "ACCELERATING" in detail
    assert "BUY" in detail
    # Score lines use the real contribution values.
    assert "+15" in detail


def test_no_trade_missing_checklist() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=4.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    expl = snap.explainability
    assert expl is not None
    assert expl.headline == "NO TRADE"
    assert "✗ Stability" in expl.checklist
    assert "✓ Feed" in expl.checklist
    assert "✓ Assessment" in expl.checklist


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
    breakdown = BuyScoreBreakdown(20, 15, 0, 0, 0, 0)
    evidence = capture_score_evidence(
        _assessment(DecisionAssessmentState.BLOCKED), None, None, None
    )
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
            evidence=evidence,
        )


def test_sell_internal_detail_confirms_sell_physics() -> None:
    history = ((95, 95), (96, 96))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _sell_context(),
        _physics(velocity=-2.5, acceleration=-1.0),
        _liquidity(
            liquidity_shift=LiquidityBias.SELL.value,
            dom_imbalance=LiquidityBias.SELL.value,
        ),
        timestamp=5.0,
        sell_signal_history=history,
    )
    assert snap.decision is TradeDecision.SELL_INTERNAL
    expl = snap.explainability
    assert expl is not None
    detail = "\n".join(expl.sell_detail_lines)
    assert "Direction          SELL" in detail
    assert "Direction Confirmed YES" in detail
    assert "SELL confirmed by" in expl.sell_reason
