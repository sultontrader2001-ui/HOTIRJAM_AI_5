"""Unit tests for Trade Decision Policy — BUY Conditions v1 (Sprint 20)."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.trade_decision import (
    TradeDecision,
    TradeDecisionEngine,
    apply_trade_decision_policy,
    evaluate_trade_decision,
    is_buy_eligible,
)
from hotirjam_ai5.trade_decision.policy import (
    BUY_CONDITIONS_SATISFIED_REASON,
    CONTEXT_UNAVAILABLE_REASON,
    NEXT_ACTION,
    NOT_AUTHORIZED_REASON,
)


def _assessment(state: DecisionAssessmentState) -> DecisionAssessmentSnapshot:
    return DecisionAssessmentSnapshot(
        timestamp=100.0,
        assessment_state=state,
        assessment_ready=state is DecisionAssessmentState.READY,
        reason="Assessment workflow observation",
        next_stage="Assessment workflow next stage",
    )


def _context(*, summary: str = "Volatile market with unstable behavior.") -> MarketContextSnapshot:
    return MarketContextSnapshot(
        timestamp=100.0,
        state="VOLATILE",
        state_reason="Rapid velocity change",
        transition="NONE",
        transition_changed=False,
        transition_duration=12.0,
        behavior="UNSTABLE",
        behavior_reason="Volatile market condition",
        feed_status="HEALTHY",
        feed_quality="GOOD",
        dom_status="HEALTHY",
        dom_quality="GOOD",
        tick_rate=8.0,
        spread=0.25,
        summary=summary,
    )


def test_assessment_not_ready_returns_no_trade() -> None:
    context = _context()
    for state in (DecisionAssessmentState.BLOCKED, DecisionAssessmentState.REVIEW):
        assessment = _assessment(state)
        assert is_buy_eligible(assessment, context) is False
        snap = apply_trade_decision_policy(assessment, context, timestamp=1.0)
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.reason == NOT_AUTHORIZED_REASON
        assert snap.next_action == NEXT_ACTION


def test_ready_with_context_missing_returns_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    assert is_buy_eligible(assessment, None) is False
    snap = apply_trade_decision_policy(assessment, None, timestamp=2.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision is not TradeDecision.BUY
    assert snap.reason == CONTEXT_UNAVAILABLE_REASON


def test_ready_with_insufficient_context_returns_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(summary="Insufficient market context.")
    assert is_buy_eligible(assessment, context) is False
    snap = apply_trade_decision_policy(assessment, context, timestamp=3.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == CONTEXT_UNAVAILABLE_REASON


def test_ready_with_context_available_satisfies_buy_conditions_but_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    assert is_buy_eligible(assessment, context) is True

    snap = apply_trade_decision_policy(assessment, context, timestamp=4.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision is not TradeDecision.BUY
    assert snap.reason == BUY_CONDITIONS_SATISFIED_REASON
    assert snap.reason == "BUY conditions satisfied. Awaiting activation."
    assert snap.next_action == NEXT_ACTION
    assert snap.timestamp == 4.0


def test_buy_never_emitted() -> None:
    context = _context()
    for state in DecisionAssessmentState:
        snap = apply_trade_decision_policy(_assessment(state), context, timestamp=5.0)
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.decision is not TradeDecision.BUY


def test_sell_remains_unavailable() -> None:
    values = {item.value for item in TradeDecision}
    assert "BUY" in values
    assert "SELL" not in values


def test_engine_delegates_to_policy() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    via_engine = evaluate_trade_decision(assessment, context, timestamp=7.0)
    via_policy = apply_trade_decision_policy(assessment, context, timestamp=7.0)
    assert via_engine == via_policy
    assert via_engine.decision is TradeDecision.NO_TRADE
    assert via_engine.reason == BUY_CONDITIONS_SATISFIED_REASON


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(_assessment(DecisionAssessmentState.READY), _context())
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == BUY_CONDITIONS_SATISFIED_REASON
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap
