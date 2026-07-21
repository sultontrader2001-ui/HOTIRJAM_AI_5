"""Unit tests for Trade Decision Engine (Sprint 15) — skeleton only."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.trade_decision import (
    TradeDecision,
    TradeDecisionEngine,
    evaluate_trade_decision,
)
from hotirjam_ai5.trade_decision.engine import (
    BLOCKED_REASON,
    NEXT_ACTION,
    READY_REASON,
    REVIEW_REASON,
)


def _assessment(state: DecisionAssessmentState) -> DecisionAssessmentSnapshot:
    return DecisionAssessmentSnapshot(
        timestamp=100.0,
        assessment_state=state,
        assessment_ready=state is DecisionAssessmentState.READY,
        reason="Assessment workflow observation",
        next_stage="Assessment workflow next stage",
    )


def test_blocked_maps_to_no_trade() -> None:
    snap = evaluate_trade_decision(
        _assessment(DecisionAssessmentState.BLOCKED),
        timestamp=1.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == BLOCKED_REASON
    assert snap.next_action == NEXT_ACTION


def test_review_maps_to_no_trade() -> None:
    snap = evaluate_trade_decision(
        _assessment(DecisionAssessmentState.REVIEW),
        timestamp=2.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == REVIEW_REASON
    assert snap.next_action == NEXT_ACTION


def test_ready_maps_to_no_trade() -> None:
    snap = evaluate_trade_decision(
        _assessment(DecisionAssessmentState.READY),
        timestamp=3.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == READY_REASON
    assert snap.next_action == NEXT_ACTION
    assert snap.timestamp == 3.0


def test_reason_generation() -> None:
    blocked = evaluate_trade_decision(
        _assessment(DecisionAssessmentState.BLOCKED),
        timestamp=4.0,
    )
    review = evaluate_trade_decision(
        _assessment(DecisionAssessmentState.REVIEW),
        timestamp=5.0,
    )
    ready = evaluate_trade_decision(
        _assessment(DecisionAssessmentState.READY),
        timestamp=6.0,
    )
    assert blocked.reason == "Assessment blocked."
    assert review.reason == "Waiting for review completion."
    assert ready.reason == "Trade logic not implemented yet."


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(_assessment(DecisionAssessmentState.READY))
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap


def test_buy_sell_long_short_are_not_implemented() -> None:
    values = {item.value for item in TradeDecision}
    assert values == {"NO_TRADE"}
    assert "BUY" not in values
    assert "SELL" not in values
    assert "LONG" not in values
    assert "SHORT" not in values


def test_output_never_contains_prohibited_words() -> None:
    banned = (
        "buy",
        "sell",
        "long",
        "short",
        "order",
        "broker",
        "position",
        "risk",
        "probability",
        "confidence",
        "stop loss",
        "take profit",
    )
    for state in DecisionAssessmentState:
        snap = evaluate_trade_decision(_assessment(state), timestamp=1.0)
        text = f"{snap.decision.value} {snap.reason} {snap.next_action}".lower()
        for word in banned:
            assert word not in text
