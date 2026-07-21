"""Trade Decision Engine — orchestrator over internal Decision Policy."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.decision_assessment import DecisionAssessmentSnapshot
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot
from hotirjam_ai5.trade_decision.policy import (
    NEXT_ACTION,
    REVIEW_REASON,
    apply_trade_decision_policy,
)


class TradeDecisionEngine:
    """Orchestrates trade decision evaluation via the internal policy.

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
        """Delegate decision logic to the internal policy."""
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
    """Orchestration entry point that delegates to Decision Policy."""
    return apply_trade_decision_policy(assessment, timestamp=timestamp)
