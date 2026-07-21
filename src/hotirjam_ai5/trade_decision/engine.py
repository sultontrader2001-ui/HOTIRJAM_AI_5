"""Trade Decision Engine — orchestrator over internal Decision Policy."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from hotirjam_ai5.decision_assessment import DecisionAssessmentSnapshot
from hotirjam_ai5.liquidity import LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision.models import (
    DecisionReadiness,
    SignalStability,
    TradeDecision,
    TradeDecisionSnapshot,
)
from hotirjam_ai5.trade_decision.policy import (
    NEXT_ACTION,
    SIGNAL_STABILITY_WINDOW,
    apply_trade_decision_policy,
    empty_decision_explanation,
)
from hotirjam_ai5.trade_decision.explainability import (
    build_decision_explainability,
    empty_score_breakdown,
)


class TradeDecisionEngine:
    """Orchestrates trade decision evaluation via the internal policy.

    Maintains separate BUY/SELL rolling stability histories.
    Emits SELL_INTERNAL or BUY_INTERNAL only when that side's readiness is READY.
    Results are observation-only — never sent to execution or a broker.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._buy_signal_history: deque[tuple[int, int]] = deque(
            maxlen=SIGNAL_STABILITY_WINDOW
        )
        self._sell_signal_history: deque[tuple[int, int]] = deque(
            maxlen=SIGNAL_STABILITY_WINDOW
        )
        explanation = empty_decision_explanation()
        zero = empty_score_breakdown()
        self._latest = TradeDecisionSnapshot(
            timestamp=self._clock(),
            decision=TradeDecision.NO_TRADE,
            reason=explanation.summary,
            next_action=NEXT_ACTION,
            buy_score=0,
            buy_confidence=0,
            sell_score=0,
            sell_confidence=0,
            signal_stability=SignalStability.UNSTABLE,
            sell_signal_stability=SignalStability.UNSTABLE,
            decision_readiness=DecisionReadiness.UNKNOWN,
            sell_decision_readiness=DecisionReadiness.UNKNOWN,
            decision_explanation=explanation,
            buy_score_breakdown=zero,
            sell_score_breakdown=zero,
            explainability=build_decision_explainability(
                decision=TradeDecision.NO_TRADE,
                buy_breakdown=zero,
                sell_breakdown=zero,
                buy_score=0,
                buy_confidence=0,
                sell_score=0,
                sell_confidence=0,
                buy_stability=SignalStability.UNSTABLE,
                buy_readiness=DecisionReadiness.UNKNOWN,
                sell_readiness=DecisionReadiness.UNKNOWN,
                decision_explanation=explanation,
            ),
        )

    def evaluate(
        self,
        assessment: DecisionAssessmentSnapshot,
        context: MarketContextSnapshot | None = None,
        physics: PhysicsSnapshot | None = None,
        liquidity: LiquiditySnapshot | None = None,
    ) -> TradeDecisionSnapshot:
        """Delegate decision logic to the internal policy with rolling history."""
        prior_buy = tuple(self._buy_signal_history)
        prior_sell = tuple(self._sell_signal_history)
        self._latest = evaluate_trade_decision(
            assessment,
            context,
            physics,
            liquidity,
            timestamp=self._clock(),
            signal_history=prior_buy,
            sell_signal_history=prior_sell,
        )
        self._buy_signal_history.append(
            (self._latest.buy_score, self._latest.buy_confidence)
        )
        self._sell_signal_history.append(
            (self._latest.sell_score, self._latest.sell_confidence)
        )
        return self._latest

    def snapshot(self) -> TradeDecisionSnapshot:
        """Return the latest trade decision without re-evaluating."""
        return self._latest


def evaluate_trade_decision(
    assessment: DecisionAssessmentSnapshot,
    context: MarketContextSnapshot | None = None,
    physics: PhysicsSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
    *,
    timestamp: float,
    signal_history: tuple[tuple[int, int], ...] = (),
    sell_signal_history: tuple[tuple[int, int], ...] = (),
) -> TradeDecisionSnapshot:
    """Orchestration entry point that delegates to Decision Policy."""
    return apply_trade_decision_policy(
        assessment,
        context,
        physics,
        liquidity,
        timestamp=timestamp,
        signal_history=signal_history,
        sell_signal_history=sell_signal_history,
    )
