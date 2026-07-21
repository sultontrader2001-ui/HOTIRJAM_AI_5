"""Decision Assessment Engine — final evaluation standardization only."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.decision_assessment.models import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.decision_evaluation import (
    DecisionEvaluationSnapshot,
    DecisionEvaluationStatus,
)

BLOCKED_REASON = "Evaluation cannot continue."
BLOCKED_NEXT_STAGE = "Decision Evaluation Engine"
REVIEW_REASON = "Evaluation complete, awaiting final decision."
REVIEW_NEXT_STAGE = "Decision Assessment Engine"
READY_REASON = "Evaluation completed successfully."
READY_NEXT_STAGE = "Trade Decision Engine"


class DecisionAssessmentEngine:
    """Maps Decision Evaluation status to a standardized assessment state.

    Consumes only DecisionEvaluationSnapshot. Never inspects lower layers.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = DecisionAssessmentSnapshot(
            timestamp=self._clock(),
            assessment_state=DecisionAssessmentState.REVIEW,
            assessment_ready=False,
            reason=REVIEW_REASON,
            next_stage=REVIEW_NEXT_STAGE,
        )

    def evaluate(
        self,
        evaluation: DecisionEvaluationSnapshot,
    ) -> DecisionAssessmentSnapshot:
        """Map the current evaluation status to assessment state."""
        self._latest = evaluate_decision_assessment(
            evaluation,
            timestamp=self._clock(),
        )
        return self._latest

    def snapshot(self) -> DecisionAssessmentSnapshot:
        """Return the latest assessment without re-evaluating."""
        return self._latest


def evaluate_decision_assessment(
    evaluation: DecisionEvaluationSnapshot,
    *,
    timestamp: float,
) -> DecisionAssessmentSnapshot:
    """Pure status mapping from DecisionEvaluationSnapshot only."""
    if evaluation.status is DecisionEvaluationStatus.WAITING:
        return DecisionAssessmentSnapshot(
            timestamp=timestamp,
            assessment_state=DecisionAssessmentState.BLOCKED,
            assessment_ready=False,
            reason=BLOCKED_REASON,
            next_stage=BLOCKED_NEXT_STAGE,
        )

    if evaluation.status is DecisionEvaluationStatus.IDLE:
        return DecisionAssessmentSnapshot(
            timestamp=timestamp,
            assessment_state=DecisionAssessmentState.REVIEW,
            assessment_ready=False,
            reason=REVIEW_REASON,
            next_stage=REVIEW_NEXT_STAGE,
        )

    return DecisionAssessmentSnapshot(
        timestamp=timestamp,
        assessment_state=DecisionAssessmentState.READY,
        assessment_ready=True,
        reason=READY_REASON,
        next_stage=READY_NEXT_STAGE,
    )
