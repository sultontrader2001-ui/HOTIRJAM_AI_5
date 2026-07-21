"""Decision Explainability — expose real scoring breakdowns (Sprint 36).

Reads values already computed by Trade Decision Policy.
Never recalculates scores, never invents explanations.
"""

from __future__ import annotations

from hotirjam_ai5.trade_decision.models import (
    BuyScoreBreakdown,
    DecisionExplainability,
    DecisionExplanation,
    DecisionReadiness,
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
        ScoreContributionLine("Market State", breakdown.market_state),
        ScoreContributionLine("Behavior", breakdown.behavior),
        ScoreContributionLine("Physics", breakdown.physics),
        ScoreContributionLine("Liquidity", breakdown.liquidity),
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
) -> DecisionExplainability:
    """Build explainability from already-computed decision values only."""
    if buy_breakdown.total != buy_score:
        raise ValueError("buy_breakdown.total must match buy_score")
    if sell_breakdown.total != sell_score:
        raise ValueError("sell_breakdown.total must match sell_score")

    buy_lines = contributions_from_breakdown(buy_breakdown)
    sell_lines = contributions_from_breakdown(sell_breakdown)

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
        )

    return DecisionExplainability(
        headline="NO TRADE",
        buy_contributions=buy_lines,
        buy_total=buy_score,
        sell_contributions=sell_lines,
        sell_total=sell_score,
        checklist=_no_trade_checklist(
            buy_score=buy_score,
            buy_confidence=buy_confidence,
            buy_stability=buy_stability,
            buy_readiness=buy_readiness,
            sell_readiness=sell_readiness,
            decision_explanation=decision_explanation,
        ),
        selection_lines=(),
    )


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


def _no_trade_checklist(
    *,
    buy_score: int,
    buy_confidence: int,
    buy_stability: SignalStability,
    buy_readiness: DecisionReadiness,
    sell_readiness: DecisionReadiness,
    decision_explanation: DecisionExplanation | None,
) -> tuple[str, ...]:
    """Checklist of real readiness conditions that blocked activation."""
    from hotirjam_ai5.trade_decision.policy import (
        READINESS_MIN_BUY_CONFIDENCE,
        READINESS_MIN_BUY_SCORE,
    )

    expl = decision_explanation
    items: list[str] = []

    if buy_score >= READINESS_MIN_BUY_SCORE:
        items.append(f"✓ BUY score ≥ {READINESS_MIN_BUY_SCORE} ({buy_score})")
    else:
        items.append(f"✗ BUY score < {READINESS_MIN_BUY_SCORE} ({buy_score})")

    if buy_confidence >= READINESS_MIN_BUY_CONFIDENCE:
        items.append(
            f"✓ BUY confidence ≥ {READINESS_MIN_BUY_CONFIDENCE} ({buy_confidence})"
        )
    else:
        items.append(
            f"✗ BUY confidence < {READINESS_MIN_BUY_CONFIDENCE} ({buy_confidence})"
        )

    items.append(_status_item("Feed Healthy", expl.feed if expl else None))
    items.append(_status_item("Assessment Ready", expl.assessment if expl else None))
    items.append(_status_item("Physics confirmed", expl.physics if expl else None))
    items.append(_status_item("Liquidity confirmed", expl.liquidity if expl else None))

    if buy_stability is SignalStability.STABLE:
        items.append("✓ Stability reached")
    else:
        items.append("✗ Stability not reached")

    if buy_readiness is DecisionReadiness.READY:
        items.append("✓ BUY Decision Readiness READY")
    else:
        items.append(f"✗ BUY Decision Readiness {buy_readiness.value}")

    if sell_readiness is DecisionReadiness.READY:
        items.append("✓ SELL Decision Readiness READY")
    else:
        items.append(f"✗ SELL Decision Readiness {sell_readiness.value}")

    return tuple(items)


def _status_item(label: str, status: ExplanationStatus | None) -> str:
    if status is ExplanationStatus.PASS:
        return f"✓ {label}"
    if status is ExplanationStatus.UNKNOWN:
        return f"✗ {label} (unknown)"
    return f"✗ {label}"
