"""Unit tests for Decision Evaluation Engine (Sprint 13)."""

from __future__ import annotations

from hotirjam_ai5.decision_evaluation import (
    DecisionEvaluationEngine,
    DecisionEvaluationStatus,
    evaluate_decision_evaluation,
)
from hotirjam_ai5.decision_evaluation.engine import (
    EVALUATE_NEXT_STAGE,
    EVALUATE_REASON,
    OBSERVE_NEXT_STAGE,
    OBSERVE_REASON,
    WAIT_NEXT_STAGE,
    WAIT_REASON,
)
from hotirjam_ai5.decision_intent import DecisionIntent, DecisionIntentSnapshot


def _intent(intent: DecisionIntent) -> DecisionIntentSnapshot:
    return DecisionIntentSnapshot(
        timestamp=100.0,
        intent=intent,
        reason="Workflow observation",
        next_step="Workflow next step",
    )


def test_wait_maps_to_waiting() -> None:
    snap = evaluate_decision_evaluation(
        _intent(DecisionIntent.WAIT),
        timestamp=1.0,
    )
    assert snap.status is DecisionEvaluationStatus.WAITING
    assert snap.evaluation_allowed is False
    assert snap.reason == WAIT_REASON
    assert snap.next_stage == WAIT_NEXT_STAGE


def test_observe_maps_to_idle() -> None:
    snap = evaluate_decision_evaluation(
        _intent(DecisionIntent.OBSERVE),
        timestamp=2.0,
    )
    assert snap.status is DecisionEvaluationStatus.IDLE
    assert snap.evaluation_allowed is False
    assert snap.reason == OBSERVE_REASON
    assert snap.next_stage == OBSERVE_NEXT_STAGE


def test_evaluate_maps_to_evaluating() -> None:
    snap = evaluate_decision_evaluation(
        _intent(DecisionIntent.EVALUATE),
        timestamp=3.0,
    )
    assert snap.status is DecisionEvaluationStatus.EVALUATING
    assert snap.evaluation_allowed is True
    assert snap.reason == EVALUATE_REASON
    assert snap.next_stage == EVALUATE_NEXT_STAGE
    assert snap.timestamp == 3.0


def test_status_mapping_is_exact() -> None:
    expected = {
        DecisionIntent.WAIT: DecisionEvaluationStatus.WAITING,
        DecisionIntent.OBSERVE: DecisionEvaluationStatus.IDLE,
        DecisionIntent.EVALUATE: DecisionEvaluationStatus.EVALUATING,
    }
    for intent, status in expected.items():
        snap = evaluate_decision_evaluation(_intent(intent), timestamp=4.0)
        assert snap.status is status


def test_reason_generation() -> None:
    waiting = evaluate_decision_evaluation(_intent(DecisionIntent.WAIT), timestamp=5.0)
    idle = evaluate_decision_evaluation(_intent(DecisionIntent.OBSERVE), timestamp=6.0)
    evaluating = evaluate_decision_evaluation(
        _intent(DecisionIntent.EVALUATE),
        timestamp=7.0,
    )
    assert waiting.reason == "Waiting for future conditions."
    assert idle.reason == "Evaluation not started."
    assert evaluating.reason == "Evaluation initiated."


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = DecisionEvaluationEngine(clock=clock)
    snap = engine.evaluate(_intent(DecisionIntent.EVALUATE))
    assert snap.status is DecisionEvaluationStatus.EVALUATING
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap


def test_output_never_contains_prohibited_words() -> None:
    banned = (
        "buy",
        "sell",
        "long",
        "short",
        "entry",
        "exit",
        "signal",
        "confidence",
        "probability",
        "risk",
    )
    for intent in DecisionIntent:
        snap = evaluate_decision_evaluation(_intent(intent), timestamp=1.0)
        text = (
            f"{snap.status.value} {snap.reason} {snap.next_stage}"
        ).lower()
        for word in banned:
            assert word not in text
