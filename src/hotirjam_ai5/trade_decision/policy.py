"""Trade Decision Policy v2 + Trade Authorization v1.

Internal authorization stage lives here — not a separate engine.
BUY and SELL are intentionally not implemented.
NO_TRADE remains a deliberate operational outcome.
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


DENIED_REASON = "Trading policy not authorized."
PENDING_REASON = "Trading authorization pending."
GRANTED_REASON = "Trading authorized. Awaiting first strategy."
NEXT_ACTION = "Execution Engine"

# Backward-compatible aliases for orchestrator defaults.
REVIEW_REASON = PENDING_REASON


def resolve_trade_authorization(
    assessment: DecisionAssessmentSnapshot,
) -> TradeAuthorization:
    """Map assessment state to the internal authorization stage."""
    if assessment.assessment_state is DecisionAssessmentState.BLOCKED:
        return TradeAuthorization.DENIED
    if assessment.assessment_state is DecisionAssessmentState.REVIEW:
        return TradeAuthorization.PENDING
    return TradeAuthorization.GRANTED


def _reason_for_authorization(authorization: TradeAuthorization) -> str:
    if authorization is TradeAuthorization.DENIED:
        return DENIED_REASON
    if authorization is TradeAuthorization.PENDING:
        return PENDING_REASON
    return GRANTED_REASON


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Apply authorization, then emit intentional NO_TRADE with operational reason.

    Authorization:
      BLOCKED → DENIED  → Trading policy not authorized.
      REVIEW  → PENDING → Trading authorization pending.
      READY   → GRANTED → Trading authorized. Awaiting first strategy.
    """
    authorization = resolve_trade_authorization(assessment)
    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=TradeDecision.NO_TRADE,
        reason=_reason_for_authorization(authorization),
        next_action=NEXT_ACTION,
    )
