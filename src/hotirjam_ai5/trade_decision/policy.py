"""Trade Decision Policy v1 — internal decision rules only.

BUY and SELL are intentionally not implemented.
"""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot

BLOCKED_REASON = "Assessment blocked."
REVIEW_REASON = "Review incomplete."
READY_REASON = "Waiting for first trading policy."
NEXT_ACTION = "Execution Engine"


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Apply the internal NO_TRADE policy from assessment state only."""
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
