"""Unit tests for Trade Decision Policy — BUY Strategy Phase 3 (Sprint 22)."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision import (
    TradeDecision,
    TradeDecisionEngine,
    apply_trade_decision_policy,
    evaluate_trade_decision,
    is_buy_eligible,
    matches_buy_strategy,
)
from hotirjam_ai5.trade_decision.policy import (
    BUY_STRATEGY_VALIDATED_REASON,
    NEXT_ACTION,
    NOT_AUTHORIZED_REASON,
    STRATEGY_NOT_SATISFIED_REASON,
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
) -> MarketContextSnapshot:
    return MarketContextSnapshot(
        timestamp=100.0,
        state=state,
        state_reason="Structured field fixture",
        transition="NONE",
        transition_changed=False,
        transition_duration=12.0,
        behavior=behavior,
        behavior_reason="Structured field fixture",
        feed_status=feed_status,
        feed_quality="GOOD",
        dom_status="HEALTHY",
        dom_quality="GOOD",
        tick_rate=8.0,
        spread=0.25,
        summary="ACTIVE market with STABLE behavior.",
    )


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


def test_ready_active_stable_positive_physics_validates_but_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="ACTIVE", behavior="STABLE")
    physics = _physics(velocity=1.5, acceleration=0.3)
    assert matches_buy_strategy(context, physics) is True
    assert is_buy_eligible(assessment, context, physics) is True

    snap = apply_trade_decision_policy(
        assessment, context, physics, timestamp=1.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision is not TradeDecision.BUY
    assert snap.reason == BUY_STRATEGY_VALIDATED_REASON
    assert snap.reason == "BUY strategy validated. Awaiting release."
    assert snap.next_action == NEXT_ACTION


def test_negative_velocity_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    physics = _physics(velocity=-0.5, acceleration=0.2)
    assert matches_buy_strategy(context, physics) is False
    assert is_buy_eligible(assessment, context, physics) is False

    snap = apply_trade_decision_policy(
        assessment, context, physics, timestamp=2.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_negative_acceleration_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    physics = _physics(velocity=1.0, acceleration=-0.1)
    assert matches_buy_strategy(context, physics) is False

    snap = apply_trade_decision_policy(
        assessment, context, physics, timestamp=3.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_zero_physics_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    for physics in (
        _physics(velocity=0.0, acceleration=0.2),
        _physics(velocity=1.0, acceleration=0.0),
    ):
        assert matches_buy_strategy(context, physics) is False
        snap = apply_trade_decision_policy(
            assessment, context, physics, timestamp=4.0
        )
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_ready_volatile_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="VOLATILE", behavior="STABLE")
    physics = _physics()
    assert matches_buy_strategy(context, physics) is False

    snap = apply_trade_decision_policy(
        assessment, context, physics, timestamp=5.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_ready_unstable_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="ACTIVE", behavior="UNSTABLE")
    physics = _physics()
    assert matches_buy_strategy(context, physics) is False

    snap = apply_trade_decision_policy(
        assessment, context, physics, timestamp=6.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_feed_unhealthy_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(feed_status="DEGRADED")
    physics = _physics()
    assert matches_buy_strategy(context, physics) is False

    snap = apply_trade_decision_policy(
        assessment, context, physics, timestamp=7.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_assessment_not_ready_returns_no_trade() -> None:
    context = _context()
    physics = _physics()
    for state in (DecisionAssessmentState.BLOCKED, DecisionAssessmentState.REVIEW):
        assessment = _assessment(state)
        assert is_buy_eligible(assessment, context, physics) is False
        snap = apply_trade_decision_policy(
            assessment, context, physics, timestamp=8.0
        )
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.reason == NOT_AUTHORIZED_REASON
        assert snap.next_action == NEXT_ACTION


def test_missing_physics_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    assert matches_buy_strategy(context, None) is False
    assert is_buy_eligible(assessment, context, None) is False
    snap = apply_trade_decision_policy(assessment, context, None, timestamp=9.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_buy_never_emitted() -> None:
    context = _context()
    physics = _physics()
    for state in DecisionAssessmentState:
        snap = apply_trade_decision_policy(
            _assessment(state), context, physics, timestamp=10.0
        )
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.decision is not TradeDecision.BUY


def test_sell_remains_unavailable() -> None:
    values = {item.value for item in TradeDecision}
    assert "BUY" in values
    assert "SELL" not in values


def test_engine_delegates_to_policy() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="TRENDING", behavior="ACCELERATING")
    physics = _physics(velocity=2.0, acceleration=0.5)
    via_engine = evaluate_trade_decision(
        assessment, context, physics, timestamp=11.0
    )
    via_policy = apply_trade_decision_policy(
        assessment, context, physics, timestamp=11.0
    )
    assert via_engine == via_policy
    assert via_engine.decision is TradeDecision.NO_TRADE
    assert via_engine.reason == BUY_STRATEGY_VALIDATED_REASON


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == BUY_STRATEGY_VALIDATED_REASON
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap
