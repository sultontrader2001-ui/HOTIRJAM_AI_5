"""Trade Decision Policy — BUY/SELL Score, Confidence, Stability, Readiness.

BUY and SELL paths are mirrored observation pipelines.
Priority: SELL_INTERNAL if SELL readiness READY, else BUY_INTERNAL if BUY
readiness READY, else NO_TRADE. Tradable orders remain unavailable.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Final

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.liquidity import LiquidityBias, LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.memory.diagnostics_models import MemoryDiagnosticsReport
from hotirjam_ai5.trade_decision.explainability import (
    build_decision_explainability,
    capture_score_evidence,
)
from hotirjam_ai5.trade_decision.memory_influence import (
    apply_memory_score_influence,
)
from hotirjam_ai5.trade_decision.models import (
    BuyConfidenceBreakdown,
    BuyScoreBreakdown,
    DecisionExplanation,
    DecisionReadiness,
    ExplanationStatus,
    SellConfidenceBreakdown,
    SellScoreBreakdown,
    SignalStability,
    TradeDecision,
    TradeDecisionSnapshot,
)


class TradeAuthorization(StrEnum):
    """Internal trade authorization stage (policy-only)."""

    DENIED = "DENIED"
    PENDING = "PENDING"
    GRANTED = "GRANTED"


# --- BUY Score weights (setup quality) ---
POINTS_ASSESSMENT: Final[int] = 20
POINTS_FEED_HEALTH: Final[int] = 15
POINTS_MARKET_STATE: Final[int] = 15
POINTS_BEHAVIOR: Final[int] = 15
POINTS_PHYSICS: Final[int] = 20
POINTS_LIQUIDITY: Final[int] = 15
POINTS_TOTAL: Final[int] = 100

# --- BUY Confidence weights (decision reliability) ---
CONF_ASSESSMENT_RELIABILITY: Final[int] = 25
CONF_FEED_RELIABILITY: Final[int] = 20
CONF_PHYSICS_STABILITY: Final[int] = 20
CONF_LIQUIDITY_RELIABILITY: Final[int] = 20
CONF_MARKET_STABILITY: Final[int] = 15
CONF_TOTAL: Final[int] = 100

# --- Signal Stability (temporal confirmation) ---
SIGNAL_STABILITY_WINDOW: Final[int] = 3
SIGNAL_MIN_BUY_SCORE: Final[int] = 80
SIGNAL_MIN_BUY_CONFIDENCE: Final[int] = 85

# --- Decision Readiness (final activation gate) ---
READINESS_MIN_BUY_SCORE: Final[int] = 80
READINESS_MIN_BUY_CONFIDENCE: Final[int] = 85

NEXT_ACTION = "Execution Engine"
DEFAULT_FAIL_SUMMARY = "Market conditions do not satisfy BUY requirements."
SATISFIED_SUMMARY = (
    "BUY requirements are satisfied and Decision Readiness is READY. Awaiting release."
)
SELL_SATISFIED_SUMMARY = (
    "SELL requirements are satisfied and Decision Readiness is READY. Awaiting release."
)
READINESS_NOT_READY_SUMMARY = "Decision Readiness is NOT_READY."
READINESS_UNKNOWN_SUMMARY = "Decision Readiness is UNKNOWN."

_ELIGIBLE_STATES: Final[frozenset[str]] = frozenset({"ACTIVE", "TRENDING"})
_ELIGIBLE_BEHAVIORS: Final[frozenset[str]] = frozenset({"STABLE", "ACCELERATING"})
_HEALTHY_FEED: Final[str] = "HEALTHY"
_BUY_BIAS: Final[str] = LiquidityBias.BUY.value
_SELL_BIAS: Final[str] = LiquidityBias.SELL.value

# Sprint 35 — signed direction values from Market State / Behavior.
_STATE_DIRECTION_UP: Final[str] = "UP"
_STATE_DIRECTION_DOWN: Final[str] = "DOWN"
_BEHAVIOR_DIRECTION_BUY: Final[str] = "BUY"
_BEHAVIOR_DIRECTION_SELL: Final[str] = "SELL"


def _state_qualifies(context: MarketContextSnapshot, *, side: str) -> bool:
    """Directional market-state check (Sprint 35).

    Eligible regime AND matching sign. NEUTRAL direction awards neither side.
    """
    if context.state not in _ELIGIBLE_STATES:
        return False
    expected = _STATE_DIRECTION_DOWN if side == "SELL" else _STATE_DIRECTION_UP
    return context.state_direction == expected


def _behavior_qualifies(context: MarketContextSnapshot, *, side: str) -> bool:
    """Directional behavior check (Sprint 35).

    Eligible behavior AND matching sign. NEUTRAL direction awards neither side.
    """
    if context.behavior not in _ELIGIBLE_BEHAVIORS:
        return False
    expected = (
        _BEHAVIOR_DIRECTION_SELL if side == "SELL" else _BEHAVIOR_DIRECTION_BUY
    )
    return context.behavior_direction == expected


def format_buy_score_reason(score: int) -> str:
    """Format the NO_TRADE reason for a computed BUY score."""
    return f"BUY score: {score}/100. Awaiting release."


def empty_decision_explanation() -> DecisionExplanation:
    """Default explanation before inputs are available."""
    return DecisionExplanation(
        assessment=ExplanationStatus.UNKNOWN,
        feed=ExplanationStatus.UNKNOWN,
        market_state=ExplanationStatus.UNKNOWN,
        behavior=ExplanationStatus.UNKNOWN,
        physics=ExplanationStatus.UNKNOWN,
        liquidity=ExplanationStatus.UNKNOWN,
        signal_stability=ExplanationStatus.UNKNOWN,
        readiness=ExplanationStatus.UNKNOWN,
        summary=READINESS_UNKNOWN_SUMMARY,
    )


PENDING_REASON = format_buy_score_reason(0)


def qualifies_for_signal_stability(buy_score: int, buy_confidence: int) -> bool:
    """Return True when one evaluation meets stability thresholds."""
    return (
        buy_score >= SIGNAL_MIN_BUY_SCORE
        and buy_confidence >= SIGNAL_MIN_BUY_CONFIDENCE
    )


def resolve_signal_stability(
    history: Sequence[tuple[int, int]],
) -> SignalStability:
    """Resolve STABLE/UNSTABLE from a rolling score/confidence history.

    STABLE only when the window is full and every sample qualifies.
    """
    if len(history) < SIGNAL_STABILITY_WINDOW:
        return SignalStability.UNSTABLE
    window = history[-SIGNAL_STABILITY_WINDOW:]
    if all(qualifies_for_signal_stability(score, conf) for score, conf in window):
        return SignalStability.STABLE
    return SignalStability.UNSTABLE


def signal_stability_explanation_status(
    stability: SignalStability,
    *,
    history_length: int,
) -> ExplanationStatus:
    """Map signal stability to explanation PASS/FAIL/UNKNOWN."""
    if history_length < SIGNAL_STABILITY_WINDOW:
        return ExplanationStatus.UNKNOWN
    if stability is SignalStability.STABLE:
        return ExplanationStatus.PASS
    return ExplanationStatus.FAIL


def resolve_decision_readiness(
    *,
    buy_score: int,
    buy_confidence: int,
    signal_stability: SignalStability,
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None,
    liquidity: LiquiditySnapshot | None,
    signal_stability_status: ExplanationStatus,
    liquidity_bias: str = _BUY_BIAS,
) -> DecisionReadiness:
    """Resolve directional pipeline readiness for signal activation.

    UNKNOWN when feed or liquidity inputs are unavailable, or stability
    has not yet accumulated a full confirmation window.
    """
    if (
        context is None
        or liquidity is None
        or signal_stability_status is ExplanationStatus.UNKNOWN
    ):
        return DecisionReadiness.UNKNOWN

    feed_pass = context.feed_status == _HEALTHY_FEED
    liquidity_pass = (
        liquidity.liquidity_shift == liquidity_bias
        and liquidity.dom_imbalance == liquidity_bias
    )
    assessment_ready = (
        assessment.assessment_state is DecisionAssessmentState.READY
    )

    if (
        buy_score >= READINESS_MIN_BUY_SCORE
        and buy_confidence >= READINESS_MIN_BUY_CONFIDENCE
        and signal_stability is SignalStability.STABLE
        and assessment_ready
        and feed_pass
        and liquidity_pass
    ):
        return DecisionReadiness.READY
    return DecisionReadiness.NOT_READY


def decision_readiness_explanation_status(
    readiness: DecisionReadiness,
) -> ExplanationStatus:
    """Map decision readiness to explanation PASS/FAIL/UNKNOWN."""
    if readiness is DecisionReadiness.READY:
        return ExplanationStatus.PASS
    if readiness is DecisionReadiness.UNKNOWN:
        return ExplanationStatus.UNKNOWN
    return ExplanationStatus.FAIL


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
    """Score each BUY setup-quality category (binary full points or zero)."""
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
        if _state_qualifies(context, side="BUY"):
            state_pts = POINTS_MARKET_STATE
        if _behavior_qualifies(context, side="BUY"):
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


def compute_buy_confidence(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> BuyConfidenceBreakdown:
    """Compute decision reliability independently from buy_score.

    Never calls compute_buy_score. Uses confidence-specific weights/categories.
    """
    assessment_pts = (
        CONF_ASSESSMENT_RELIABILITY
        if assessment.assessment_state is DecisionAssessmentState.READY
        else 0
    )

    feed_pts = 0
    market_pts = 0
    if context is not None:
        if context.feed_status == _HEALTHY_FEED:
            feed_pts = CONF_FEED_RELIABILITY
        if _state_qualifies(context, side="BUY") and _behavior_qualifies(
            context, side="BUY"
        ):
            market_pts = CONF_MARKET_STABILITY

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
            physics_pts = CONF_PHYSICS_STABILITY

    liquidity_pts = 0
    if liquidity is not None:
        if (
            liquidity.liquidity_shift == _BUY_BIAS
            and liquidity.dom_imbalance == _BUY_BIAS
        ):
            liquidity_pts = CONF_LIQUIDITY_RELIABILITY

    return BuyConfidenceBreakdown(
        assessment_reliability=assessment_pts,
        feed_reliability=feed_pts,
        physics_stability=physics_pts,
        liquidity_reliability=liquidity_pts,
        market_stability=market_pts,
    )


def compute_sell_score(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> SellScoreBreakdown:
    """Score each SELL setup-quality category (mirrored BUY weights)."""
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
        if _state_qualifies(context, side="SELL"):
            state_pts = POINTS_MARKET_STATE
        if _behavior_qualifies(context, side="SELL"):
            behavior_pts = POINTS_BEHAVIOR

    physics_pts = 0
    if physics is not None:
        velocity = physics.tick_velocity
        acceleration = physics.tick_acceleration
        if (
            velocity is not None
            and acceleration is not None
            and velocity < 0
            and acceleration < 0
        ):
            physics_pts = POINTS_PHYSICS

    liquidity_pts = 0
    if liquidity is not None:
        if (
            liquidity.liquidity_shift == _SELL_BIAS
            and liquidity.dom_imbalance == _SELL_BIAS
        ):
            liquidity_pts = POINTS_LIQUIDITY

    return SellScoreBreakdown(
        assessment=assessment_pts,
        feed_health=feed_pts,
        market_state=state_pts,
        behavior=behavior_pts,
        physics=physics_pts,
        liquidity=liquidity_pts,
    )


def compute_sell_confidence(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> SellConfidenceBreakdown:
    """Compute SELL decision reliability independently from sell_score."""
    assessment_pts = (
        CONF_ASSESSMENT_RELIABILITY
        if assessment.assessment_state is DecisionAssessmentState.READY
        else 0
    )

    feed_pts = 0
    market_pts = 0
    if context is not None:
        if context.feed_status == _HEALTHY_FEED:
            feed_pts = CONF_FEED_RELIABILITY
        if _state_qualifies(context, side="SELL") and _behavior_qualifies(
            context, side="SELL"
        ):
            market_pts = CONF_MARKET_STABILITY

    physics_pts = 0
    if physics is not None:
        velocity = physics.tick_velocity
        acceleration = physics.tick_acceleration
        if (
            velocity is not None
            and acceleration is not None
            and velocity < 0
            and acceleration < 0
        ):
            physics_pts = CONF_PHYSICS_STABILITY

    liquidity_pts = 0
    if liquidity is not None:
        if (
            liquidity.liquidity_shift == _SELL_BIAS
            and liquidity.dom_imbalance == _SELL_BIAS
        ):
            liquidity_pts = CONF_LIQUIDITY_RELIABILITY

    return SellConfidenceBreakdown(
        assessment_reliability=assessment_pts,
        feed_reliability=feed_pts,
        physics_stability=physics_pts,
        liquidity_reliability=liquidity_pts,
        market_stability=market_pts,
    )


def _status_from_bool(ok: bool) -> ExplanationStatus:
    return ExplanationStatus.PASS if ok else ExplanationStatus.FAIL


def build_decision_explanation(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
    *,
    signal_stability_status: ExplanationStatus = ExplanationStatus.UNKNOWN,
    readiness_status: ExplanationStatus = ExplanationStatus.UNKNOWN,
    side: str = "BUY",
) -> DecisionExplanation:
    """Build PASS/FAIL/UNKNOWN explanation for the selected side."""
    assessment_status = _status_from_bool(
        assessment.assessment_state is DecisionAssessmentState.READY
    )

    if context is None:
        feed_status = ExplanationStatus.UNKNOWN
        state_status = ExplanationStatus.UNKNOWN
        behavior_status = ExplanationStatus.UNKNOWN
    else:
        feed_status = _status_from_bool(context.feed_status == _HEALTHY_FEED)
        state_status = _status_from_bool(_state_qualifies(context, side=side))
        behavior_status = _status_from_bool(_behavior_qualifies(context, side=side))

    if physics is None:
        physics_status = ExplanationStatus.UNKNOWN
    else:
        velocity = physics.tick_velocity
        acceleration = physics.tick_acceleration
        if velocity is None or acceleration is None:
            physics_status = ExplanationStatus.UNKNOWN
        elif side == "SELL":
            physics_status = _status_from_bool(velocity < 0 and acceleration < 0)
        else:
            physics_status = _status_from_bool(velocity > 0 and acceleration > 0)

    if liquidity is None:
        liquidity_status = ExplanationStatus.UNKNOWN
    else:
        bias = _SELL_BIAS if side == "SELL" else _BUY_BIAS
        liquidity_status = _status_from_bool(
            liquidity.liquidity_shift == bias and liquidity.dom_imbalance == bias
        )

    summary = _build_explanation_summary(
        assessment_status=assessment_status,
        feed_status=feed_status,
        state_status=state_status,
        behavior_status=behavior_status,
        physics_status=physics_status,
        liquidity_status=liquidity_status,
        signal_stability_status=signal_stability_status,
        readiness_status=readiness_status,
        context=context,
        side=side,
    )
    return DecisionExplanation(
        assessment=assessment_status,
        feed=feed_status,
        market_state=state_status,
        behavior=behavior_status,
        physics=physics_status,
        liquidity=liquidity_status,
        signal_stability=signal_stability_status,
        readiness=readiness_status,
        summary=summary,
    )


def _build_explanation_summary(
    *,
    assessment_status: ExplanationStatus,
    feed_status: ExplanationStatus,
    state_status: ExplanationStatus,
    behavior_status: ExplanationStatus,
    physics_status: ExplanationStatus,
    liquidity_status: ExplanationStatus,
    signal_stability_status: ExplanationStatus,
    readiness_status: ExplanationStatus,
    context: MarketContextSnapshot | None,
    side: str = "BUY",
) -> str:
    """Produce a concise sentence explaining the decision."""
    statuses = (
        assessment_status,
        feed_status,
        state_status,
        behavior_status,
        physics_status,
        liquidity_status,
        signal_stability_status,
        readiness_status,
    )
    if all(status is ExplanationStatus.PASS for status in statuses):
        return SELL_SATISFIED_SUMMARY if side == "SELL" else SATISFIED_SUMMARY

    if readiness_status is ExplanationStatus.UNKNOWN:
        return READINESS_UNKNOWN_SUMMARY

    if readiness_status is ExplanationStatus.FAIL:
        label = "SELL" if side == "SELL" else "BUY"
        if signal_stability_status is ExplanationStatus.FAIL:
            return (
                f"{label} signal is not yet stable across consecutive evaluations. "
                + READINESS_NOT_READY_SUMMARY
            )
        return READINESS_NOT_READY_SUMMARY

    if (
        context is not None
        and context.state == "VOLATILE"
        and state_status is ExplanationStatus.FAIL
        and physics_status is ExplanationStatus.UNKNOWN
    ):
        return "Market is volatile and physics confirmation is missing."

    if (
        context is not None
        and context.state == "VOLATILE"
        and state_status is ExplanationStatus.FAIL
        and physics_status is ExplanationStatus.FAIL
    ):
        return "Market is volatile and physics confirmation failed."

    if assessment_status is ExplanationStatus.FAIL and all(
        status is not ExplanationStatus.FAIL
        for status in (
            feed_status,
            state_status,
            behavior_status,
            physics_status,
            liquidity_status,
            signal_stability_status,
            readiness_status,
        )
    ):
        return "Assessment is not READY for trade decision."

    if side == "SELL":
        return "Market conditions do not satisfy SELL requirements."
    return DEFAULT_FAIL_SUMMARY


def matches_buy_strategy(
    context: MarketContextSnapshot | None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> bool:
    """Return True when context + physics + liquidity each score full BUY points."""
    if context is None or physics is None or liquidity is None:
        return False
    velocity = physics.tick_velocity
    acceleration = physics.tick_acceleration
    if velocity is None or acceleration is None:
        return False
    return (
        context.feed_status == _HEALTHY_FEED
        and _state_qualifies(context, side="BUY")
        and _behavior_qualifies(context, side="BUY")
        and velocity > 0
        and acceleration > 0
        and liquidity.liquidity_shift == _BUY_BIAS
        and liquidity.dom_imbalance == _BUY_BIAS
    )


def matches_sell_strategy(
    context: MarketContextSnapshot | None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> bool:
    """Return True when context + physics + liquidity each score full SELL points."""
    if context is None or physics is None or liquidity is None:
        return False
    velocity = physics.tick_velocity
    acceleration = physics.tick_acceleration
    if velocity is None or acceleration is None:
        return False
    return (
        context.feed_status == _HEALTHY_FEED
        and _state_qualifies(context, side="SELL")
        and _behavior_qualifies(context, side="SELL")
        and velocity < 0
        and acceleration < 0
        and liquidity.liquidity_shift == _SELL_BIAS
        and liquidity.dom_imbalance == _SELL_BIAS
    )


def is_buy_eligible(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> bool:
    """True when buy_score reaches 100."""
    return compute_buy_score(assessment, context, physics, liquidity).total == POINTS_TOTAL


def resolve_trade_decision(
    sell_readiness: DecisionReadiness,
    buy_readiness: DecisionReadiness = DecisionReadiness.NOT_READY,
) -> TradeDecision:
    """Priority: SELL_INTERNAL, else BUY_INTERNAL, else NO_TRADE."""
    if sell_readiness is DecisionReadiness.READY:
        return TradeDecision.SELL_INTERNAL
    if buy_readiness is DecisionReadiness.READY:
        return TradeDecision.BUY_INTERNAL
    return TradeDecision.NO_TRADE


def apply_trade_decision_policy(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
    *,
    timestamp: float,
    signal_history: Sequence[tuple[int, int]] = (),
    sell_signal_history: Sequence[tuple[int, int]] = (),
    memory_diagnostics: MemoryDiagnosticsReport | None = None,
) -> TradeDecisionSnapshot:
    """Compute BUY and SELL pipelines; emit observation-only activation.

    Memory Diagnostics may apply a capped secondary score adjustment (Sprint 44).
    Primary category math is unchanged. Memory never invents a decision on its own.
    """
    buy_breakdown = compute_buy_score(assessment, context, physics, liquidity)
    original_buy_score = buy_breakdown.total
    buy_confidence = compute_buy_confidence(
        assessment, context, physics, liquidity
    ).total

    sell_breakdown = compute_sell_score(assessment, context, physics, liquidity)
    original_sell_score = sell_breakdown.total
    sell_confidence = compute_sell_confidence(
        assessment, context, physics, liquidity
    ).total

    memory_influence = apply_memory_score_influence(
        original_buy_score=original_buy_score,
        original_sell_score=original_sell_score,
        report=memory_diagnostics,
    )
    buy_score = memory_influence.adjusted_buy_score
    sell_score = memory_influence.adjusted_sell_score

    buy_history = (*signal_history, (buy_score, buy_confidence))
    buy_stability = resolve_signal_stability(buy_history)
    buy_stability_status = signal_stability_explanation_status(
        buy_stability,
        history_length=len(buy_history),
    )
    buy_readiness = resolve_decision_readiness(
        buy_score=buy_score,
        buy_confidence=buy_confidence,
        signal_stability=buy_stability,
        assessment=assessment,
        context=context,
        liquidity=liquidity,
        signal_stability_status=buy_stability_status,
        liquidity_bias=_BUY_BIAS,
    )

    sell_history = (*sell_signal_history, (sell_score, sell_confidence))
    sell_stability = resolve_signal_stability(sell_history)
    sell_stability_status = signal_stability_explanation_status(
        sell_stability,
        history_length=len(sell_history),
    )
    sell_readiness = resolve_decision_readiness(
        buy_score=sell_score,
        buy_confidence=sell_confidence,
        signal_stability=sell_stability,
        assessment=assessment,
        context=context,
        liquidity=liquidity,
        signal_stability_status=sell_stability_status,
        liquidity_bias=_SELL_BIAS,
    )

    # Directional physics/liquidity make dual READY impossible; guard anyway.
    if (
        buy_readiness is DecisionReadiness.READY
        and sell_readiness is DecisionReadiness.READY
    ):
        sell_readiness = DecisionReadiness.NOT_READY

    decision = resolve_trade_decision(sell_readiness, buy_readiness)
    if decision is TradeDecision.SELL_INTERNAL:
        side = "SELL"
        stability_status = sell_stability_status
        readiness_status = decision_readiness_explanation_status(sell_readiness)
    else:
        side = "BUY"
        stability_status = buy_stability_status
        readiness_status = decision_readiness_explanation_status(buy_readiness)

    explanation = build_decision_explanation(
        assessment,
        context,
        physics,
        liquidity,
        signal_stability_status=stability_status,
        readiness_status=readiness_status,
        side=side,
    )
    evidence = capture_score_evidence(assessment, context, physics, liquidity)
    # Explainability stays tied to primary breakdown totals (pre-Memory).
    explainability = build_decision_explainability(
        decision=decision,
        buy_breakdown=buy_breakdown,
        sell_breakdown=sell_breakdown,
        buy_score=original_buy_score,
        buy_confidence=buy_confidence,
        sell_score=original_sell_score,
        sell_confidence=sell_confidence,
        buy_stability=buy_stability,
        buy_readiness=buy_readiness,
        sell_readiness=sell_readiness,
        decision_explanation=explanation,
        evidence=evidence,
    )
    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=decision,
        reason=explanation.summary,
        next_action=NEXT_ACTION,
        buy_score=buy_score,
        buy_confidence=buy_confidence,
        sell_score=sell_score,
        sell_confidence=sell_confidence,
        signal_stability=buy_stability,
        sell_signal_stability=sell_stability,
        decision_readiness=buy_readiness,
        sell_decision_readiness=sell_readiness,
        decision_explanation=explanation,
        buy_score_breakdown=buy_breakdown,
        sell_score_breakdown=sell_breakdown,
        explainability=explainability,
        memory_influence=memory_influence,
    )
