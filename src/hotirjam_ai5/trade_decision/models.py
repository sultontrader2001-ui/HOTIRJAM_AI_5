"""Trade decision models.

Trade Decision Engine output values. SELL remains unavailable.
BUY exists for future emission; Sprint 19 does not emit BUY yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TradeDecision(StrEnum):
    """Trade decision output. SELL is intentionally unavailable."""

    NO_TRADE = "NO_TRADE"
    BUY = "BUY"


@dataclass(frozen=True, slots=True)
class TradeDecisionSnapshot:
    """Trade decision derived from Decision Assessment only."""

    timestamp: float
    decision: TradeDecision
    reason: str
    next_action: str
