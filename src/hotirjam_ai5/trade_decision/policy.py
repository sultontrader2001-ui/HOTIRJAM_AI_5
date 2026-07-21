"""Trade Decision Policy v2 — rule-based NO_TRADE decisions.

BUY and SELL are intentionally not implemented.
NO_TRADE is a deliberate operational outcome with explicit reasons.
"""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot

# Rule-based operational reasons (never placeholder "not implemented" text).
BLOCKED_REASON = "Decision assessment blocked."
REVIEW_REASON = "Decision assessment still under review."
READY_REASON = "Trading policy not yet authorized."
NEXT_ACTION = "Execution Engine"


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Apply rule-based NO_TRADE policy from assessment state only.

    Rule 1: BLOCKED → NO_TRADE (assessment blocked)
    Rule 2: REVIEW  → NO_TRADE (still under review)
    Rule 3: READY   → NO_TRADE (trading policy not yet authorized)
    """
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
