"""Unit tests for Decision Assessment Engine (Sprint 14)."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentEngine,
    DecisionAssessmentState,
    evaluate_decision_assessment,
)
from hotirjam_ai5.decision_assessment.engine import (
    BLOCKED_NEXT_STAGE,
    BLOCKED_REASON,
    READY_NEXT_STAGE,
    READY_REASON,
    REVIEW_NEXT_STAGE,
    REVIEW_REASON,
)
from hotirjam_ai5.decision_evaluation import (
    DecisionEvaluationSnapshot,
    DecisionEvaluationStatus,
)


def _evaluation(status: DecisionEvaluationStatus) -> DecisionEvaluationSnapshot:
    return DecisionEvaluationSnapshot(
        timestamp=100.0,
        status=status,
        evaluation_allowed=status is DecisionEvaluationStatus.EVALUATING,
        reason="Evaluation workflow observation",
        next_stage="Evaluation workflow next stage",
    )


def test_waiting_maps_to_blocked() -> None:
    snap = evaluate_decision_assessment(
        _evaluation(DecisionEvaluationStatus.WAITING),
        timestamp=1.0,
    )
    assert snap.assessment_state is DecisionAssessmentState.BLOCKED
    assert snap.assessment_ready is False
    assert snap.reason == BLOCKED_REASON
    assert snap.next_stage == BLOCKED_NEXT_STAGE


def test_idle_maps_to_review() -> None:
    snap = evaluate_decision_assessment(
        _evaluation(DecisionEvaluationStatus.IDLE),
        timestamp=2.0,
    )
    assert snap.assessment_state is DecisionAssessmentState.REVIEW
    assert snap.assessment_ready is False
    assert snap.reason == REVIEW_REASON
    assert snap.next_stage == REVIEW_NEXT_STAGE


def test_evaluating_maps_to_ready() -> None:
    snap = evaluate_decision_assessment(
        _evaluation(DecisionEvaluationStatus.EVALUATING),
        timestamp=3.0,
    )
    assert snap.assessment_state is DecisionAssessmentState.READY
    assert snap.assessment_ready is True
    assert snap.reason == READY_REASON
    assert snap.next_stage == READY_NEXT_STAGE
    assert snap.timestamp == 3.0


def test_status_mapping_is_exact() -> None:
    expected = {
        DecisionEvaluationStatus.WAITING: DecisionAssessmentState.BLOCKED,
        DecisionEvaluationStatus.IDLE: DecisionAssessmentState.REVIEW,
        DecisionEvaluationStatus.EVALUATING: DecisionAssessmentState.READY,
    }
    for status, assessment_state in expected.items():
        snap = evaluate_decision_assessment(_evaluation(status), timestamp=4.0)
        assert snap.assessment_state is assessment_state


def test_reason_and_next_stage_generation() -> None:
    blocked = evaluate_decision_assessment(
        _evaluation(DecisionEvaluationStatus.WAITING),
        timestamp=5.0,
    )
    review = evaluate_decision_assessment(
        _evaluation(DecisionEvaluationStatus.IDLE),
        timestamp=6.0,
    )
    ready = evaluate_decision_assessment(
        _evaluation(DecisionEvaluationStatus.EVALUATING),
        timestamp=7.0,
    )
    assert blocked.reason == "Evaluation cannot continue."
    assert blocked.next_stage == "Decision Evaluation Engine"
    assert review.reason == "Evaluation complete, awaiting final decision."
    assert review.next_stage == "Decision Assessment Engine"
    assert ready.reason == "Evaluation completed successfully."
    assert ready.next_stage == "Trade Decision Engine"


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = DecisionAssessmentEngine(clock=clock)
    snap = engine.evaluate(_evaluation(DecisionEvaluationStatus.EVALUATING))
    assert snap.assessment_state is DecisionAssessmentState.READY
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
        "order",
        "position",
        "risk",
        "probability",
        "confidence",
    )
    for status in DecisionEvaluationStatus:
        snap = evaluate_decision_assessment(_evaluation(status), timestamp=1.0)
        text = (
            f"{snap.assessment_state.value} {snap.reason} {snap.next_stage}"
        ).lower()
        for word in banned:
            assert word not in text
