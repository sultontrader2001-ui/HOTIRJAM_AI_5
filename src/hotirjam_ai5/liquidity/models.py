"""Liquidity observation models.

Produced by LiquidityEngine from DOM. Consumed by Trade Decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LiquidityBias(StrEnum):
    """Directional liquidity bias used by BUY filters."""

    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class LiquiditySnapshot:
    """Immutable liquidity observation for trade-decision filters.

    Produced only by LiquidityEngine from DOM. Trade Decision never
    computes liquidity from Tick/DOM/Physics itself.
    """

    timestamp: float
    liquidity_shift: str
    dom_imbalance: str
    confidence: float
