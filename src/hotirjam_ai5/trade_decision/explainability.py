"""Decision Explainability — expose real scoring evidence (Sprint 36/38).

Reads values already computed by Trade Decision Policy.
Never recalculates scores, never invents explanations.
"""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import DecisionAssessmentSnapshot
from hotirjam_ai5.liquidity import LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision.models import (
    BuyScoreBreakdown,
    DecisionExplainability,
    DecisionExplanation,
    DecisionReadiness,
    DecisionScoreEvidence,
    ExplanationStatus,
    ScoreContributionLine,
    SellScoreBreakdown,
    SignalStability,
    TradeDecision,
)


def empty_score_breakdown() -> BuyScoreBreakdown:
    """Zero breakdown before any evaluation."""
    return BuyScoreBreakdown(
        assessment=0,
        feed_health=0,
        market_state=0,
        behavior=0,
        physics=0,
        liquidity=0,
    )


def contributions_from_breakdown(
    breakdown: BuyScoreBreakdown | SellScoreBreakdown,
) -> tuple[ScoreContributionLine, ...]:
    """Map a real score breakdown to labeled contribution lines."""
    return (
        ScoreContributionLine("Assessment", breakdown.assessment),
        ScoreContributionLine("Feed", breakdown.feed_health),
        ScoreContributionLine("State", breakdown.market_state),
        ScoreContributionLine("Behavior", breakdown.behavior),
        ScoreContributionLine("Physics", breakdown.physics),
        ScoreContributionLine("Liquidity", breakdown.liquidity),
    )


def capture_score_evidence(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None,
    physics: PhysicsSnapshot | None,
    liquidity: LiquiditySnapshot | None,
) -> DecisionScoreEvidence:
    """Snapshot the exact inputs used for scoring (no derived scores)."""
    return DecisionScoreEvidence(
        assessment_state=assessment.assessment_state.value,
        feed_status=context.feed_status if context is not None else "UNKNOWN",
        feed_latency_ms=(
            context.tick_delay_ms if context is not None else None
        ),
        market_state=context.state if context is not None else "UNKNOWN",
        state_direction=(
            context.state_direction if context is not None else "NEUTRAL"
        ),
        behavior=context.behavior if context is not None else "UNKNOWN",
        behavior_direction=(
            context.behavior_direction if context is not None else "NEUTRAL"
        ),
        tick_velocity=physics.tick_velocity if physics is not None else None,
        tick_acceleration=(
            physics.tick_acceleration if physics is not None else None
        ),
        liquidity_shift=(
            liquidity.liquidity_shift if liquidity is not None else None
        ),
        dom_imbalance=(
            liquidity.dom_imbalance if liquidity is not None else None
        ),
    )


def build_decision_explainability(
    *,
    decision: TradeDecision,
    buy_breakdown: BuyScoreBreakdown,
    sell_breakdown: SellScoreBreakdown,
    buy_score: int,
    buy_confidence: int,
    sell_score: int,
    sell_confidence: int,
    buy_stability: SignalStability,
    buy_readiness: DecisionReadiness,
    sell_readiness: DecisionReadiness,
    decision_explanation: DecisionExplanation | None,
    evidence: DecisionScoreEvidence,
) -> DecisionExplainability:
    """Build explainability from already-computed decision values only."""
    if buy_breakdown.total != buy_score:
        raise ValueError("buy_breakdown.total must match buy_score")
    if sell_breakdown.total != sell_score:
        raise ValueError("sell_breakdown.total must match sell_score")

    buy_lines = contributions_from_breakdown(buy_breakdown)
    sell_lines = contributions_from_breakdown(sell_breakdown)
    buy_details = _side_detail_lines(side="BUY", breakdown=buy_breakdown, evidence=evidence)
    sell_details = _side_detail_lines(
        side="SELL", breakdown=sell_breakdown, evidence=evidence
    )
    buy_reason = _confirmed_reason("BUY", buy_breakdown)
    sell_reason = _confirmed_reason("SELL", sell_breakdown)

    if decision is TradeDecision.BUY_INTERNAL:
        return DecisionExplainability(
            headline="BUY selected because",
            buy_contributions=buy_lines,
            buy_total=buy_score,
            sell_contributions=sell_lines,
            sell_total=sell_score,
            checklist=(),
            selection_lines=_selection_lines_buy(
                buy_breakdown=buy_breakdown,
                buy_score=buy_score,
                buy_confidence=buy_confidence,
                sell_score=sell_score,
            ),
            buy_detail_lines=buy_details,
            sell_detail_lines=sell_details,
            buy_reason=buy_reason,
            sell_reason=sell_reason,
            evidence=evidence,
        )

    if decision is TradeDecision.SELL_INTERNAL:
        return DecisionExplainability(
            headline="SELL selected because",
            buy_contributions=buy_lines,
            buy_total=buy_score,
            sell_contributions=sell_lines,
            sell_total=sell_score,
            checklist=(),
            selection_lines=_selection_lines_sell(
                sell_breakdown=sell_breakdown,
                sell_score=sell_score,
                sell_confidence=sell_confidence,
                buy_score=buy_score,
            ),
            buy_detail_lines=buy_details,
            sell_detail_lines=sell_details,
            buy_reason=buy_reason,
            sell_reason=sell_reason,
            evidence=evidence,
        )

    return DecisionExplainability(
        headline="NO TRADE",
        buy_contributions=buy_lines,
        buy_total=buy_score,
        sell_contributions=sell_lines,
        sell_total=sell_score,
        checklist=_no_trade_missing(
            buy_stability=buy_stability,
            decision_explanation=decision_explanation,
        ),
        selection_lines=(),
        buy_detail_lines=buy_details,
        sell_detail_lines=sell_details,
        buy_reason=buy_reason,
        sell_reason=sell_reason,
        evidence=evidence,
    )


def _side_detail_lines(
    *,
    side: str,
    breakdown: BuyScoreBreakdown | SellScoreBreakdown,
    evidence: DecisionScoreEvidence,
) -> tuple[str, ...]:
    """Detailed category reasoning for one side, using captured evidence."""
    lines: list[str] = []
    lines.extend(_assessment_block(evidence, breakdown.assessment))
    lines.extend(_feed_block(evidence, breakdown.feed_health))
    lines.extend(_state_block(evidence, breakdown.market_state))
    lines.extend(_behavior_block(evidence, breakdown.behavior))
    lines.extend(_physics_block(side, evidence, breakdown.physics))
    lines.extend(_liquidity_block(side, evidence, breakdown.liquidity))
    lines.append(side)
    for contrib in contributions_from_breakdown(breakdown):
        lines.append(f"{contrib.label:<14} +{contrib.points}")
    lines.append(f"{'TOTAL':<14} {breakdown.total}")
    lines.append("Reason")
    lines.append(_confirmed_reason(side, breakdown))
    return tuple(lines)


def _assessment_block(evidence: DecisionScoreEvidence, score: int) -> list[str]:
    return [
        "Assessment",
        evidence.assessment_state,
        "Score",
        f"+{score}",
    ]


def _feed_block(evidence: DecisionScoreEvidence, score: int) -> list[str]:
    if evidence.feed_latency_ms is None:
        latency = "—"
    else:
        latency = f"{evidence.feed_latency_ms:.0f} ms"
    return [
        "Feed",
        evidence.feed_status,
        "Latency",
        latency,
        "Score",
        f"+{score}",
    ]


def _state_block(evidence: DecisionScoreEvidence, score: int) -> list[str]:
    return [
        "State",
        evidence.market_state,
        "Direction",
        evidence.state_direction,
        "Score",
        f"+{score}",
    ]


def _behavior_block(evidence: DecisionScoreEvidence, score: int) -> list[str]:
    return [
        "Behavior",
        evidence.behavior,
        "Direction",
        evidence.behavior_direction,
        "Score",
        f"+{score}",
    ]


def _physics_block(
    side: str,
    evidence: DecisionScoreEvidence,
    score: int,
) -> list[str]:
    velocity = evidence.tick_velocity
    acceleration = evidence.tick_acceleration
    if side == "BUY":
        v_ok = velocity is not None and velocity > 0
        a_ok = acceleration is not None and acceleration > 0
        direction = "BUY" if v_ok and a_ok else "NONE"
    else:
        v_ok = velocity is not None and velocity < 0
        a_ok = acceleration is not None and acceleration < 0
        direction = "SELL" if v_ok and a_ok else "NONE"

    return [
        "Physics",
        f"Velocity           {_fmt_signed(velocity)} {_mark(v_ok, velocity)}",
        f"Acceleration       {_fmt_signed(acceleration)} {_mark(a_ok, acceleration)}",
        f"Direction          {direction}",
        f"Score              +{score}",
    ]


def _liquidity_block(
    side: str,
    evidence: DecisionScoreEvidence,
    score: int,
) -> list[str]:
    shift = evidence.liquidity_shift or "—"
    imbalance = evidence.dom_imbalance or "—"
    expected = "BUY" if side == "BUY" else "SELL"
    confirmed = (
        evidence.liquidity_shift == expected
        and evidence.dom_imbalance == expected
    )
    return [
        "Liquidity",
        f"Liquidity Shift    {shift}",
        f"DOM Imbalance      {imbalance}",
        f"Direction Confirmed {'YES' if confirmed else 'NO'}",
        f"Score              +{score}",
    ]


def _fmt_signed(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}"


def _mark(ok: bool, value: float | None) -> str:
    if value is None:
        return "✗"
    return "✓" if ok else "✗"


def _confirmed_reason(
    side: str,
    breakdown: BuyScoreBreakdown | SellScoreBreakdown,
) -> str:
    """Directional confirmation only (State / Behavior / Physics / Liquidity)."""
    confirmed: list[str] = []
    if breakdown.market_state > 0:
        confirmed.append("Market State")
    if breakdown.behavior > 0:
        confirmed.append("Behavior")
    if breakdown.physics > 0:
        confirmed.append("Physics")
    if breakdown.liquidity > 0:
        confirmed.append("Liquidity")
    if not confirmed:
        return f"{side} not confirmed by Market State, Behavior, Physics, or Liquidity."
    joined = ",\n".join(confirmed)
    return f"{side} confirmed by\n{joined}."


def _selection_lines_buy(
    *,
    buy_breakdown: BuyScoreBreakdown,
    buy_score: int,
    buy_confidence: int,
    sell_score: int,
) -> tuple[str, ...]:
    lines: list[str] = []
    if buy_breakdown.physics > 0:
        lines.append("Physics confirmed BUY")
    if buy_breakdown.liquidity > 0:
        lines.append("Liquidity confirmed BUY")
    lines.append(f"BUY score {buy_score}")
    lines.append(f"BUY confidence {buy_confidence}%")
    lines.append(f"SELL score {sell_score}")
    return tuple(lines)


def _selection_lines_sell(
    *,
    sell_breakdown: SellScoreBreakdown,
    sell_score: int,
    sell_confidence: int,
    buy_score: int,
) -> tuple[str, ...]:
    lines: list[str] = []
    if sell_breakdown.physics > 0:
        lines.append("Physics confirmed SELL")
    if sell_breakdown.liquidity > 0:
        lines.append("Liquidity confirmed SELL")
    lines.append(f"SELL score {sell_score}")
    lines.append(f"SELL confidence {sell_confidence}%")
    lines.append(f"BUY score {buy_score}")
    return tuple(lines)


def _no_trade_missing(
    *,
    buy_stability: SignalStability,
    decision_explanation: DecisionExplanation | None,
) -> tuple[str, ...]:
    """Compact Missing checklist for NO_TRADE (Sprint 38)."""
    expl = decision_explanation
    items = [
        _missing_item("Physics confirmation", expl.physics if expl else None),
        _missing_item("Liquidity confirmation", expl.liquidity if expl else None),
    ]
    if buy_stability is SignalStability.STABLE:
        items.append("✓ Stability")
    else:
        items.append("✗ Stability")
    items.append(_missing_item("Feed", expl.feed if expl else None))
    items.append(_missing_item("Assessment", expl.assessment if expl else None))
    return tuple(items)


def _missing_item(label: str, status: ExplanationStatus | None) -> str:
    if status is ExplanationStatus.PASS:
        return f"✓ {label}"
    return f"✗ {label}"
