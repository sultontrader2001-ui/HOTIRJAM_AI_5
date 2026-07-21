"""Decision Evaluation Engine — evaluation lifecycle only."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.decision_evaluation.models import (
    DecisionEvaluationSnapshot,
    DecisionEvaluationStatus,
)
from hotirjam_ai5.decision_intent import DecisionIntent, DecisionIntentSnapshot

WAIT_REASON = "Waiting for future conditions."
WAIT_NEXT_STAGE = "Decision Intent Engine"
OBSERVE_REASON = "Evaluation not started."
OBSERVE_NEXT_STAGE = "Continue Observation"
EVALUATE_REASON = "Evaluation initiated."
EVALUATE_NEXT_STAGE = "Decision Assessment Engine"


class DecisionEvaluationEngine:
    """Maps Decision Intent to evaluation lifecycle state.

    Consumes only DecisionIntentSnapshot. Never inspects lower layers.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = DecisionEvaluationSnapshot(
            timestamp=self._clock(),
            status=DecisionEvaluationStatus.IDLE,
            evaluation_allowed=False,
            reason=OBSERVE_REASON,
            next_stage=OBSERVE_NEXT_STAGE,
        )

    def evaluate(
        self,
        intent: DecisionIntentSnapshot,
    ) -> DecisionEvaluationSnapshot:
        """Map the current intent to evaluation status."""
        self._latest = evaluate_decision_evaluation(intent, timestamp=self._clock())
        return self._latest

    def snapshot(self) -> DecisionEvaluationSnapshot:
        """Return the latest evaluation state without re-evaluating."""
        return self._latest


def evaluate_decision_evaluation(
    intent: DecisionIntentSnapshot,
    *,
    timestamp: float,
) -> DecisionEvaluationSnapshot:
    """Pure status mapping from DecisionIntentSnapshot only."""
    if intent.intent is DecisionIntent.WAIT:
        return DecisionEvaluationSnapshot(
            timestamp=timestamp,
            status=DecisionEvaluationStatus.WAITING,
            evaluation_allowed=False,
            reason=WAIT_REASON,
            next_stage=WAIT_NEXT_STAGE,
        )

    if intent.intent is DecisionIntent.OBSERVE:
        return DecisionEvaluationSnapshot(
            timestamp=timestamp,
            status=DecisionEvaluationStatus.IDLE,
            evaluation_allowed=False,
            reason=OBSERVE_REASON,
            next_stage=OBSERVE_NEXT_STAGE,
        )

    return DecisionEvaluationSnapshot(
        timestamp=timestamp,
        status=DecisionEvaluationStatus.EVALUATING,
        evaluation_allowed=True,
        reason=EVALUATE_REASON,
        next_stage=EVALUATE_NEXT_STAGE,
    )
