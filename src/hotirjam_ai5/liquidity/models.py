"""Liquidity observation models (Sprint 23).

Snapshot contract only — no liquidity engine in this sprint.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LiquidityBias(StrEnum):
    """Directional liquidity bias used by BUY Phase-4 filters."""

    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class LiquiditySnapshot:
    """Immutable liquidity observation for trade-decision filters.

    Produced by a future observation layer. Trade Decision consumes this
    snapshot only — it does not compute liquidity from Tick/DOM/Physics.
    """

    timestamp: float
    liquidity_shift: str
    dom_imbalance: str
