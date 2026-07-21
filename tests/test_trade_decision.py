"""Unit tests for Trade Decision Engine + Policy v2 (Sprint 17)."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.trade_decision import (
    TradeDecision,
    TradeDecisionEngine,
    apply_trade_decision_policy,
    evaluate_trade_decision,
)
from hotirjam_ai5.trade_decision.policy import (
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


def test_rule_blocked_no_trade() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.BLOCKED),
        timestamp=1.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == BLOCKED_REASON
    assert snap.reason == "Decision assessment blocked."
    assert snap.next_action == NEXT_ACTION


def test_rule_review_no_trade() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.REVIEW),
        timestamp=2.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == REVIEW_REASON
    assert snap.reason == "Decision assessment still under review."
    assert snap.next_action == NEXT_ACTION


def test_rule_ready_no_trade() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        timestamp=3.0,
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == READY_REASON
    assert snap.reason == "Trading policy not yet authorized."
    assert snap.next_action == NEXT_ACTION
    assert snap.timestamp == 3.0


def test_reason_mapping_is_operational() -> None:
    reasons = {
        DecisionAssessmentState.BLOCKED: "Decision assessment blocked.",
        DecisionAssessmentState.REVIEW: "Decision assessment still under review.",
        DecisionAssessmentState.READY: "Trading policy not yet authorized.",
    }
    for state, expected in reasons.items():
        snap = apply_trade_decision_policy(_assessment(state), timestamp=4.0)
        assert snap.reason == expected
        assert "not implemented" not in snap.reason.lower()
        assert "placeholder" not in snap.reason.lower()


def test_engine_delegates_to_policy() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    via_engine = evaluate_trade_decision(assessment, timestamp=7.0)
    via_policy = apply_trade_decision_policy(assessment, timestamp=7.0)
    assert via_engine == via_policy
    assert via_engine.decision is TradeDecision.NO_TRADE
    assert via_engine.reason == READY_REASON


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(_assessment(DecisionAssessmentState.READY))
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == READY_REASON
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
