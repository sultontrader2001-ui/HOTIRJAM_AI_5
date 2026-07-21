"""Trade Decision Policy + Authorization + First BUY Rule framework.

BUY path exists internally when assessment is READY, but Sprint 19 still
emits NO_TRADE only. SELL remains unavailable.
"""

from __future__ import annotations

from enum import StrEnum

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot


class TradeAuthorization(StrEnum):
    """Internal trade authorization stage (policy-only)."""

    DENIED = "DENIED"
    PENDING = "PENDING"
    GRANTED = "GRANTED"


NOT_AUTHORIZED_REASON = "Trading not authorized."
BUY_FRAMEWORK_REASON = "BUY rule framework initialized."
NEXT_ACTION = "Execution Engine"

# Orchestrator default (assessment not READY → pending authorization).
PENDING_REASON = NOT_AUTHORIZED_REASON


def resolve_trade_authorization(
    assessment: DecisionAssessmentSnapshot,
) -> TradeAuthorization:
    """Map assessment state to the internal authorization stage."""
    if assessment.assessment_state is DecisionAssessmentState.BLOCKED:
        return TradeAuthorization.DENIED
    if assessment.assessment_state is DecisionAssessmentState.REVIEW:
        return TradeAuthorization.PENDING
    return TradeAuthorization.GRANTED


def is_buy_eligible(assessment: DecisionAssessmentSnapshot) -> bool:
    """Return True when the BUY path is technically eligible (assessment READY).

    Eligibility does not emit BUY in Sprint 19.
    """
    return (
        resolve_trade_authorization(assessment) is TradeAuthorization.GRANTED
        and assessment.assessment_state is DecisionAssessmentState.READY
    )


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Apply authorization and BUY framework rules; emit NO_TRADE only.

    Rule A: Assessment != READY → NO_TRADE (Trading not authorized.)
    Rule B: Assessment == READY → BUY eligible internally, still NO_TRADE
            (BUY rule framework initialized.)
    """
    if assessment.assessment_state is not DecisionAssessmentState.READY:
        reason = NOT_AUTHORIZED_REASON
    else:
        # BUY path is initialized / eligible, but BUY is not emitted yet.
        _ = is_buy_eligible(assessment)
        reason = BUY_FRAMEWORK_REASON

    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=TradeDecision.NO_TRADE,
        reason=reason,
        next_action=NEXT_ACTION,
    )
