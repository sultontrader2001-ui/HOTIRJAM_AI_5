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


class TradeDecisionEngine:
    """Orchestrates trade decision evaluation via the internal policy.

    Maintains a rolling signal-stability history inside Trade Decision.
    Always returns NO_TRADE. Never places orders or connects to a broker.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._signal_history: deque[tuple[int, int]] = deque(
            maxlen=SIGNAL_STABILITY_WINDOW
        )
        explanation = empty_decision_explanation()
        self._latest = TradeDecisionSnapshot(
            timestamp=self._clock(),
            decision=TradeDecision.NO_TRADE,
            reason=explanation.summary,
            next_action=NEXT_ACTION,
            buy_score=0,
            buy_confidence=0,
            signal_stability=SignalStability.UNSTABLE,
            decision_explanation=explanation,
        )

    def evaluate(
        self,
        assessment: DecisionAssessmentSnapshot,
        context: MarketContextSnapshot | None = None,
        physics: PhysicsSnapshot | None = None,
        liquidity: LiquiditySnapshot | None = None,
    ) -> TradeDecisionSnapshot:
        """Delegate decision logic to the internal policy with rolling history."""
        prior_history = tuple(self._signal_history)
        self._latest = evaluate_trade_decision(
            assessment,
            context,
            physics,
            liquidity,
            timestamp=self._clock(),
            signal_history=prior_history,
        )
        self._signal_history.append(
            (self._latest.buy_score, self._latest.buy_confidence)
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
) -> TradeDecisionSnapshot:
    """Orchestration entry point that delegates to Decision Policy."""
    return apply_trade_decision_policy(
        assessment,
        context,
        physics,
        liquidity,
        timestamp=timestamp,
        signal_history=signal_history,
    )
