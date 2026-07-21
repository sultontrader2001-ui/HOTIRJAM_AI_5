"""Trade Decision Policy — Structured BUY Strategy v1.

BUY is internally eligible when assessment is READY and structured
MarketContext fields match the Phase-2 strategy. Summary text is never inspected.
Sprint 21 still emits NO_TRADE only. SELL remains unavailable.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

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
STRATEGY_NOT_SATISFIED_REASON = "BUY strategy not satisfied."
BUY_STRATEGY_VALIDATED_REASON = "BUY strategy validated. Awaiting release."
NEXT_ACTION = "Execution Engine"

# Orchestrator default (assessment not READY).
PENDING_REASON = NOT_AUTHORIZED_REASON

_ELIGIBLE_STATES: Final[frozenset[str]] = frozenset({"ACTIVE", "TRENDING"})
_ELIGIBLE_BEHAVIORS: Final[frozenset[str]] = frozenset({"STABLE", "ACCELERATING"})
_HEALTHY_FEED: Final[str] = "HEALTHY"


def resolve_trade_authorization(
    assessment: DecisionAssessmentSnapshot,
) -> TradeAuthorization:
    """Map assessment state to the internal authorization stage."""
    if assessment.assessment_state is DecisionAssessmentState.BLOCKED:
        return TradeAuthorization.DENIED
    if assessment.assessment_state is DecisionAssessmentState.REVIEW:
        return TradeAuthorization.PENDING
    return TradeAuthorization.GRANTED


def matches_buy_strategy(context: MarketContextSnapshot | None) -> bool:
    """Return True when structured MarketContext fields match BUY Phase 2.

    Uses context.state, context.behavior, and context.feed_status only.
    Never inspects summary text.
    """
    if context is None:
        return False
    return (
        context.feed_status == _HEALTHY_FEED
        and context.state in _ELIGIBLE_STATES
        and context.behavior in _ELIGIBLE_BEHAVIORS
    )


def is_buy_eligible(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
) -> bool:
    """BUY eligible when assessment is READY and structured strategy matches.

    Eligibility does not emit BUY in Sprint 21.
    """
    return (
        assessment.assessment_state is DecisionAssessmentState.READY
        and resolve_trade_authorization(assessment) is TradeAuthorization.GRANTED
        and matches_buy_strategy(context)
    )


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Apply structured BUY Phase-2 strategy; emit NO_TRADE only.

    Even when strategy matches, output remains NO_TRADE (Awaiting release).
    """
    if assessment.assessment_state is not DecisionAssessmentState.READY:
        reason = NOT_AUTHORIZED_REASON
    elif not matches_buy_strategy(context):
        reason = STRATEGY_NOT_SATISFIED_REASON
    else:
        assert is_buy_eligible(assessment, context)
        reason = BUY_STRATEGY_VALIDATED_REASON

    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=TradeDecision.NO_TRADE,
        reason=reason,
        next_action=NEXT_ACTION,
    )
