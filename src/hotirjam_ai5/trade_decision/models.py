"""Trade decision models.

Trade Decision Engine output values. SELL remains unavailable.
BUY exists for future emission; score/confidence do not emit BUY yet.
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
    """Per-category BUY score contributions (setup quality, max 100)."""

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
class BuyConfidenceBreakdown:
    """Per-category BUY confidence contributions (decision reliability, max 100)."""

    assessment_reliability: int
    feed_reliability: int
    physics_stability: int
    liquidity_reliability: int
    market_stability: int

    @property
    def total(self) -> int:
        return (
            self.assessment_reliability
            + self.feed_reliability
            + self.physics_stability
            + self.liquidity_reliability
            + self.market_stability
        )


@dataclass(frozen=True, slots=True)
class TradeDecisionSnapshot:
    """Trade decision derived from assessment, context, physics, and liquidity."""

    timestamp: float
    decision: TradeDecision
    reason: str
    next_action: str
    buy_score: int = 0
    buy_confidence: int = 0
