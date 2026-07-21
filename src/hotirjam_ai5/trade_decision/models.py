"""Trade decision models (Sprint 15).

Architecture skeleton only — never executes trades or places orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TradeDecision(StrEnum):
    """Trade decision output. BUY/SELL are intentionally absent in v1."""

    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True, slots=True)
class TradeDecisionSnapshot:
    """Trade decision derived from Decision Assessment only."""

    timestamp: float
    decision: TradeDecision
    reason: str
    next_action: str
