"""Trade Decision Engine — architecture skeleton only."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot

BLOCKED_REASON = "Assessment blocked."
REVIEW_REASON = "Waiting for review completion."
READY_REASON = "Trade logic not implemented yet."
NEXT_ACTION = "Execution Engine"


class TradeDecisionEngine:
    """Maps Decision Assessment to a trade decision skeleton.

    Consumes only DecisionAssessmentSnapshot.
    Always returns NO_TRADE in v1. Never places orders or connects to a broker.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = TradeDecisionSnapshot(
            timestamp=self._clock(),
            decision=TradeDecision.NO_TRADE,
            reason=REVIEW_REASON,
            next_action=NEXT_ACTION,
        )

    def evaluate(
        self,
        assessment: DecisionAssessmentSnapshot,
    ) -> TradeDecisionSnapshot:
        """Derive the trade decision skeleton from assessment only."""
        self._latest = evaluate_trade_decision(assessment, timestamp=self._clock())
        return self._latest

    def snapshot(self) -> TradeDecisionSnapshot:
        """Return the latest trade decision without re-evaluating."""
        return self._latest


def evaluate_trade_decision(
    assessment: DecisionAssessmentSnapshot,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Pure mapping from DecisionAssessmentSnapshot. Always NO_TRADE in v1."""
    if assessment.assessment_state is DecisionAssessmentState.BLOCKED:
        reason = BLOCKED_REASON
    elif assessment.assessment_state is DecisionAssessmentState.REVIEW:
        reason = REVIEW_REASON
    else:
        reason = READY_REASON

    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=TradeDecision.NO_TRADE,
        reason=reason,
        next_action=NEXT_ACTION,
    )
