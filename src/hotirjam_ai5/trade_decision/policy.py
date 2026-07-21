"""Trade Decision Policy — BUY Strategy Scoring Framework.

Computes a structured buy_score (0–100) from assessment, MarketContext,
Physics, and Liquidity. Always emits NO_TRADE. SELL remains unavailable.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.liquidity import LiquidityBias, LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision.models import (
    BuyScoreBreakdown,
    TradeDecision,
    TradeDecisionSnapshot,
)


class TradeAuthorization(StrEnum):
    """Internal trade authorization stage (policy-only)."""

    DENIED = "DENIED"
    PENDING = "PENDING"
    GRANTED = "GRANTED"


POINTS_ASSESSMENT: Final[int] = 20
POINTS_FEED_HEALTH: Final[int] = 15
POINTS_MARKET_STATE: Final[int] = 15
POINTS_BEHAVIOR: Final[int] = 15
POINTS_PHYSICS: Final[int] = 20
POINTS_LIQUIDITY: Final[int] = 15
POINTS_TOTAL: Final[int] = 100

NEXT_ACTION = "Execution Engine"

_ELIGIBLE_STATES: Final[frozenset[str]] = frozenset({"ACTIVE", "TRENDING"})
_ELIGIBLE_BEHAVIORS: Final[frozenset[str]] = frozenset({"STABLE", "ACCELERATING"})
_HEALTHY_FEED: Final[str] = "HEALTHY"
_BUY_BIAS: Final[str] = LiquidityBias.BUY.value


def format_buy_score_reason(score: int) -> str:
    """Format the NO_TRADE reason for a computed BUY score."""
    return f"BUY score: {score}/100. Awaiting release."


PENDING_REASON = format_buy_score_reason(0)


def resolve_trade_authorization(
    assessment: DecisionAssessmentSnapshot,
) -> TradeAuthorization:
    """Map assessment state to the internal authorization stage."""
    if assessment.assessment_state is DecisionAssessmentState.BLOCKED:
        return TradeAuthorization.DENIED
    if assessment.assessment_state is DecisionAssessmentState.REVIEW:
        return TradeAuthorization.PENDING
    return TradeAuthorization.GRANTED


def compute_buy_score(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> BuyScoreBreakdown:
    """Score each BUY category independently (binary full points or zero)."""
    assessment_pts = (
        POINTS_ASSESSMENT
        if assessment.assessment_state is DecisionAssessmentState.READY
        else 0
    )

    feed_pts = 0
    state_pts = 0
    behavior_pts = 0
    if context is not None:
        if context.feed_status == _HEALTHY_FEED:
            feed_pts = POINTS_FEED_HEALTH
        if context.state in _ELIGIBLE_STATES:
            state_pts = POINTS_MARKET_STATE
        if context.behavior in _ELIGIBLE_BEHAVIORS:
            behavior_pts = POINTS_BEHAVIOR

    physics_pts = 0
    if physics is not None:
        velocity = physics.tick_velocity
        acceleration = physics.tick_acceleration
        if (
            velocity is not None
            and acceleration is not None
            and velocity > 0
            and acceleration > 0
        ):
            physics_pts = POINTS_PHYSICS

    liquidity_pts = 0
    if liquidity is not None:
        if (
            liquidity.liquidity_shift == _BUY_BIAS
            and liquidity.dom_imbalance == _BUY_BIAS
        ):
            liquidity_pts = POINTS_LIQUIDITY

    return BuyScoreBreakdown(
        assessment=assessment_pts,
        feed_health=feed_pts,
        market_state=state_pts,
        behavior=behavior_pts,
        physics=physics_pts,
        liquidity=liquidity_pts,
    )


def matches_buy_strategy(
    context: MarketContextSnapshot | None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> bool:
    """Return True when context + physics + liquidity each score full points.

    Assessment is checked separately via is_buy_eligible / compute_buy_score.
    """
    if context is None or physics is None or liquidity is None:
        return False
    velocity = physics.tick_velocity
    acceleration = physics.tick_acceleration
    if velocity is None or acceleration is None:
        return False
    return (
        context.feed_status == _HEALTHY_FEED
        and context.state in _ELIGIBLE_STATES
        and context.behavior in _ELIGIBLE_BEHAVIORS
        and velocity > 0
        and acceleration > 0
        and liquidity.liquidity_shift == _BUY_BIAS
        and liquidity.dom_imbalance == _BUY_BIAS
    )


def is_buy_eligible(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> bool:
    """True when buy_score reaches 100. Does not emit BUY."""
    return compute_buy_score(assessment, context, physics, liquidity).total == POINTS_TOTAL


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
    *,
    timestamp: float,
) -> TradeDecisionSnapshot:
    """Compute buy_score and emit NO_TRADE with score reason."""
    breakdown = compute_buy_score(assessment, context, physics, liquidity)
    score = breakdown.total
    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=TradeDecision.NO_TRADE,
        reason=format_buy_score_reason(score),
        next_action=NEXT_ACTION,
        buy_score=score,
    )
