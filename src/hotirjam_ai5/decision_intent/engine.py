"""Decision Intent Engine — workflow controller only."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.decision_foundation import DecisionFoundationSnapshot
from hotirjam_ai5.decision_intent.models import DecisionIntent, DecisionIntentSnapshot

WAIT_REASON = "Observation layer is not ready."
WAIT_NEXT = "No further processing."
OBSERVE_REASON = "Observation stable."
OBSERVE_NEXT = "Continue monitoring."
EVALUATE_REASON = "Observation layer complete."
EVALUATE_NEXT = "Begin evaluation when available."


class DecisionIntentEngine:
    """Maps Decision Foundation readiness to the next workflow intent.

    Consumes only DecisionFoundationSnapshot. Never trades or scores.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = DecisionIntentSnapshot(
            timestamp=self._clock(),
            intent=DecisionIntent.WAIT,
            reason=WAIT_REASON,
            next_step=WAIT_NEXT,
        )

    def evaluate(
        self,
        foundation: DecisionFoundationSnapshot | None,
    ) -> DecisionIntentSnapshot:
        """Derive the next workflow intent from Decision Foundation only."""
        self._latest = evaluate_decision_intent(foundation, timestamp=self._clock())
        return self._latest

    def snapshot(self) -> DecisionIntentSnapshot:
        """Return the latest intent without re-evaluating."""
        return self._latest


def evaluate_decision_intent(
    foundation: DecisionFoundationSnapshot | None,
    *,
    timestamp: float,
) -> DecisionIntentSnapshot:
    """Pure intent mapping from DecisionFoundationSnapshot fields only."""
    if foundation is None or not foundation.ready:
        return DecisionIntentSnapshot(
            timestamp=timestamp,
            intent=DecisionIntent.WAIT,
            reason=WAIT_REASON,
            next_step=WAIT_NEXT,
        )

    if (
        foundation.observation_complete
        and foundation.required_data_complete
        and foundation.context_valid
    ):
        return DecisionIntentSnapshot(
            timestamp=timestamp,
            intent=DecisionIntent.EVALUATE,
            reason=EVALUATE_REASON,
            next_step=EVALUATE_NEXT,
        )

    return DecisionIntentSnapshot(
        timestamp=timestamp,
        intent=DecisionIntent.OBSERVE,
        reason=OBSERVE_REASON,
        next_step=OBSERVE_NEXT,
    )
