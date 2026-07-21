"""Unit tests for Trade Decision Policy + Authorization (Sprint 18)."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.trade_decision import (
    TradeAuthorization,
    TradeDecision,
    TradeDecisionEngine,
    apply_trade_decision_policy,
    evaluate_trade_decision,
    resolve_trade_authorization,
)
from hotirjam_ai5.trade_decision.policy import (
    DENIED_REASON,
    GRANTED_REASON,
    NEXT_ACTION,
    PENDING_REASON,
)


def _assessment(state: DecisionAssessmentState) -> DecisionAssessmentSnapshot:
    return DecisionAssessmentSnapshot(
        timestamp=100.0,
        assessment_state=state,
        assessment_ready=state is DecisionAssessmentState.READY,
        reason="Assessment workflow observation",
        next_stage="Assessment workflow next stage",
    )


def test_authorization_denied() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    assert resolve_trade_authorization(assessment) is TradeAuthorization.DENIED
    snap = apply_trade_decision_policy(assessment, timestamp=1.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == DENIED_REASON
    assert snap.reason == "Trading policy not authorized."
    assert snap.next_action == NEXT_ACTION


def test_authorization_pending() -> None:
    assessment = _assessment(DecisionAssessmentState.REVIEW)
    assert resolve_trade_authorization(assessment) is TradeAuthorization.PENDING
    snap = apply_trade_decision_policy(assessment, timestamp=2.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == PENDING_REASON
    assert snap.reason == "Trading authorization pending."
    assert snap.next_action == NEXT_ACTION


def test_authorization_granted() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    assert resolve_trade_authorization(assessment) is TradeAuthorization.GRANTED
    snap = apply_trade_decision_policy(assessment, timestamp=3.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == GRANTED_REASON
    assert snap.reason == "Trading authorized. Awaiting first strategy."
    assert snap.next_action == NEXT_ACTION
    assert snap.timestamp == 3.0


def test_authorization_reason_mapping() -> None:
    expected = {
        DecisionAssessmentState.BLOCKED: (
            TradeAuthorization.DENIED,
            "Trading policy not authorized.",
        ),
        DecisionAssessmentState.REVIEW: (
            TradeAuthorization.PENDING,
            "Trading authorization pending.",
        ),
        DecisionAssessmentState.READY: (
            TradeAuthorization.GRANTED,
            "Trading authorized. Awaiting first strategy.",
        ),
    }
    for state, (authorization, reason) in expected.items():
        assessment = _assessment(state)
        assert resolve_trade_authorization(assessment) is authorization
        snap = apply_trade_decision_policy(assessment, timestamp=4.0)
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.reason == reason


def test_engine_delegates_to_policy() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    via_engine = evaluate_trade_decision(assessment, timestamp=7.0)
    via_policy = apply_trade_decision_policy(assessment, timestamp=7.0)
    assert via_engine == via_policy
    assert via_engine.decision is TradeDecision.NO_TRADE
    assert via_engine.reason == GRANTED_REASON


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(_assessment(DecisionAssessmentState.READY))
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == GRANTED_REASON
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
        "not implemented",
    )
    for state in DecisionAssessmentState:
        snap = apply_trade_decision_policy(_assessment(state), timestamp=1.0)
        text = f"{snap.decision.value} {snap.reason} {snap.next_action}".lower()
        for word in banned:
            assert word not in text
