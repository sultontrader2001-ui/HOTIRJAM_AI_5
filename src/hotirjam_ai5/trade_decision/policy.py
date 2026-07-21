"""Trade Decision Policy — BUY Conditions v1.

BUY is eligible when assessment is READY and MarketContext summary is available.
Sprint 20 still emits NO_TRADE only. SELL remains unavailable.
"""

from __future__ import annotations

from enum import StrEnum

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot


class TradeAuthorization(StrEnum):
    """Internal trade authorization stage (policy-only)."""

    DENIED = "DENIED"
    PENDING = "PENDING"
    GRANTED = "GRANTED"


NOT_AUTHORIZED_REASON = "Trading not authorized."
CONTEXT_UNAVAILABLE_REASON = "Market context unavailable."
BUY_CONDITIONS_SATISFIED_REASON = "BUY conditions satisfied. Awaiting activation."
NEXT_ACTION = "Execution Engine"

# Orchestrator default (assessment not READY).
PENDING_REASON = NOT_AUTHORIZED_REASON

_INSUFFICIENT_CONTEXT = "Insufficient market context."


def resolve_trade_authorization(
    assessment: DecisionAssessmentSnapshot,
) -> TradeAuthorization:
    """Map assessment state to the internal authorization stage."""
    if assessment.assessment_state is DecisionAssessmentState.BLOCKED:
        return TradeAuthorization.DENIED
    if assessment.assessment_state is DecisionAssessmentState.REVIEW:
        return TradeAuthorization.PENDING
    return TradeAuthorization.GRANTED


def is_market_context_available(context: MarketContextSnapshot | None) -> bool:
    """Return True when MarketContext provides a usable summary."""
    if context is None:
        return False
    summary = context.summary.strip() if context.summary else ""
    if not summary:
        return False
    if summary == _INSUFFICIENT_CONTEXT:
        return False
    return True


def is_buy_eligible(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
) -> bool:
    """BUY eligible only when assessment is READY and context summary is available.

    Eligibility does not emit BUY in Sprint 20.
    """
    return (
        assessment.assessment_state is DecisionAssessmentState.READY
        and resolve_trade_authorization(assessment) is TradeAuthorization.GRANTED
        and is_market_context_available(context)
    )


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Apply BUY Phase-1 conditions; emit NO_TRADE only.

    BUY eligible when Assessment == READY and MarketContext summary is available.
    Even when eligible, output remains NO_TRADE (Awaiting activation).
    """
    if assessment.assessment_state is not DecisionAssessmentState.READY:
        reason = NOT_AUTHORIZED_REASON
    elif not is_market_context_available(context):
        reason = CONTEXT_UNAVAILABLE_REASON
    else:
        # Conditions satisfied — BUY path verified, BUY not emitted yet.
        assert is_buy_eligible(assessment, context)
        reason = BUY_CONDITIONS_SATISFIED_REASON

    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=TradeDecision.NO_TRADE,
        reason=reason,
        next_action=NEXT_ACTION,
    )
