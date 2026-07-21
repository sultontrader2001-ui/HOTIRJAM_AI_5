"""Unit tests for Trade Decision Policy — First BUY Rule framework (Sprint 19)."""

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
    is_buy_eligible,
    resolve_trade_authorization,
)
from hotirjam_ai5.trade_decision.policy import (
    BUY_FRAMEWORK_REASON,
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


def test_not_ready_returns_no_trade() -> None:
    for state in (DecisionAssessmentState.BLOCKED, DecisionAssessmentState.REVIEW):
        snap = apply_trade_decision_policy(_assessment(state), timestamp=1.0)
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.reason == NOT_AUTHORIZED_REASON
        assert snap.reason == "Trading not authorized."
        assert is_buy_eligible(_assessment(state)) is False
        assert snap.next_action == NEXT_ACTION


def test_ready_buy_path_initialized_but_no_trade_emitted() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    assert resolve_trade_authorization(assessment) is TradeAuthorization.GRANTED
    assert is_buy_eligible(assessment) is True

    snap = apply_trade_decision_policy(assessment, timestamp=2.0)
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision is not TradeDecision.BUY
    assert snap.reason == BUY_FRAMEWORK_REASON
    assert snap.reason == "BUY rule framework initialized."
    assert snap.next_action == NEXT_ACTION
    assert snap.timestamp == 2.0


def test_buy_exists_in_enum_but_is_not_emitted() -> None:
    assert TradeDecision.BUY.value == "BUY"
    for state in DecisionAssessmentState:
        snap = apply_trade_decision_policy(_assessment(state), timestamp=3.0)
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.decision is not TradeDecision.BUY


def test_sell_remains_unavailable() -> None:
    values = {item.value for item in TradeDecision}
    assert "SELL" not in values
    assert "LONG" not in values
    assert "SHORT" not in values


def test_engine_delegates_to_policy() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    via_engine = evaluate_trade_decision(assessment, timestamp=7.0)
    via_policy = apply_trade_decision_policy(assessment, timestamp=7.0)
    assert via_engine == via_policy
    assert via_engine.decision is TradeDecision.NO_TRADE
    assert via_engine.reason == BUY_FRAMEWORK_REASON


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(_assessment(DecisionAssessmentState.READY))
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == BUY_FRAMEWORK_REASON
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap


def test_output_never_emits_trading_actions() -> None:
    for state in DecisionAssessmentState:
        snap = apply_trade_decision_policy(_assessment(state), timestamp=1.0)
        assert snap.decision is TradeDecision.NO_TRADE
        lowered = f"{snap.decision.value} {snap.next_action}".lower()
        for word in ("sell", "order", "broker", "position", "risk", "probability", "confidence"):
            assert word not in lowered
