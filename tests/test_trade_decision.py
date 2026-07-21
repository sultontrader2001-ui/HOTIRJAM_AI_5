"""Unit tests for Trade Decision Policy — Structured BUY Strategy v1 (Sprint 21)."""

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
    summary: str = "ACTIVE market with STABLE behavior.",
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
        summary=summary,
    )


def test_ready_active_stable_validates_strategy_but_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="ACTIVE", behavior="STABLE")
    assert matches_buy_strategy(context) is True
    assert is_buy_eligible(assessment, context) is True

    snap = apply_trade_decision_policy(assessment, context, timestamp=1.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision is not TradeDecision.BUY
    assert snap.reason == BUY_STRATEGY_VALIDATED_REASON
    assert snap.reason == "BUY strategy validated. Awaiting release."
    assert snap.next_action == NEXT_ACTION


def test_ready_trending_accelerating_validates_strategy_but_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="TRENDING", behavior="ACCELERATING")
    assert is_buy_eligible(assessment, context) is True

    snap = apply_trade_decision_policy(assessment, context, timestamp=2.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == BUY_STRATEGY_VALIDATED_REASON


def test_ready_volatile_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="VOLATILE", behavior="STABLE")
    assert matches_buy_strategy(context) is False
    assert is_buy_eligible(assessment, context) is False

    snap = apply_trade_decision_policy(assessment, context, timestamp=3.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_ready_unstable_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="ACTIVE", behavior="UNSTABLE")
    assert matches_buy_strategy(context) is False
    assert is_buy_eligible(assessment, context) is False

    snap = apply_trade_decision_policy(assessment, context, timestamp=4.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_feed_unhealthy_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(feed_status="DEGRADED")
    assert matches_buy_strategy(context) is False
    assert is_buy_eligible(assessment, context) is False

    snap = apply_trade_decision_policy(assessment, context, timestamp=5.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON


def test_assessment_not_ready_returns_no_trade() -> None:
    context = _context()
    for state in (DecisionAssessmentState.BLOCKED, DecisionAssessmentState.REVIEW):
        assessment = _assessment(state)
        assert is_buy_eligible(assessment, context) is False
        snap = apply_trade_decision_policy(assessment, context, timestamp=6.0)
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.reason == NOT_AUTHORIZED_REASON
        assert snap.next_action == NEXT_ACTION


def test_summary_text_is_ignored() -> None:
    """Policy must not search words inside summary."""
    assessment = _assessment(DecisionAssessmentState.READY)
    # Strategy fields match even if summary says the opposite.
    context = _context(
        state="ACTIVE",
        behavior="STABLE",
        feed_status="HEALTHY",
        summary="Insufficient market context. VOLATILE UNSTABLE.",
    )
    assert is_buy_eligible(assessment, context) is True
    snap = apply_trade_decision_policy(assessment, context, timestamp=7.0)
    assert snap.reason == BUY_STRATEGY_VALIDATED_REASON

    # Strategy fields fail even if summary looks favorable.
    bad = _context(
        state="VOLATILE",
        behavior="UNSTABLE",
        feed_status="HEALTHY",
        summary="ACTIVE TRENDING STABLE ACCELERATING HEALTHY.",
    )
    assert is_buy_eligible(assessment, bad) is False
    snap_bad = apply_trade_decision_policy(assessment, bad, timestamp=8.0)
    assert snap_bad.reason == STRATEGY_NOT_SATISFIED_REASON


def test_buy_never_emitted() -> None:
    context = _context()
    for state in DecisionAssessmentState:
        snap = apply_trade_decision_policy(_assessment(state), context, timestamp=9.0)
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.decision is not TradeDecision.BUY


def test_sell_remains_unavailable() -> None:
    values = {item.value for item in TradeDecision}
    assert "BUY" in values
    assert "SELL" not in values


def test_engine_delegates_to_policy() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="TRENDING", behavior="STABLE")
    via_engine = evaluate_trade_decision(assessment, context, timestamp=10.0)
    via_policy = apply_trade_decision_policy(assessment, context, timestamp=10.0)
    assert via_engine == via_policy
    assert via_engine.decision is TradeDecision.NO_TRADE
    assert via_engine.reason == BUY_STRATEGY_VALIDATED_REASON


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(
        _assessment(DecisionAssessmentState.READY),
        _context(state="ACTIVE", behavior="ACCELERATING"),
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == BUY_STRATEGY_VALIDATED_REASON
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap


def test_missing_context_not_eligible() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    assert matches_buy_strategy(None) is False
    assert is_buy_eligible(assessment, None) is False
    snap = apply_trade_decision_policy(assessment, None, timestamp=12.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == STRATEGY_NOT_SATISFIED_REASON
