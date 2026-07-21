"""Trade decision models.

Trade Decision Engine output values. SELL remains unavailable.
BUY exists for future emission; scoring does not emit BUY yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TradeDecision(StrEnum):
    """Trade decision output. SELL is intentionally unavailable."""

    NO_TRADE = "NO_TRADE"
    BUY = "BUY"


@dataclass(frozen=True, slots=True)
class BuyScoreBreakdown:
    """Per-category BUY score contributions (max 100)."""

    assessment: int
    feed_health: int
    market_state: int
    behavior: int
    physics: int
    liquidity: int

    @property
    def total(self) -> int:
        return (
            self.assessment
            + self.feed_health
            + self.market_state
            + self.behavior
            + self.physics
            + self.liquidity
        )


@dataclass(frozen=True, slots=True)
class TradeDecisionSnapshot:
    """Trade decision derived from assessment, context, physics, and liquidity."""

    timestamp: float
    decision: TradeDecision
    reason: str
    next_action: str
    buy_score: int = 0
