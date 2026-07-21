"""Liquidity classification helpers from DOM sizes."""

from __future__ import annotations

from hotirjam_ai5.liquidity.models import LiquidityBias


def classify_bias(bid_size: int, ask_size: int) -> LiquidityBias:
    """Classify directional bias from bid vs ask size."""
    if bid_size > ask_size:
        return LiquidityBias.BUY
    if ask_size > bid_size:
        return LiquidityBias.SELL
    return LiquidityBias.NEUTRAL


def imbalance_confidence(bid_size: int, ask_size: int) -> float:
    """Return confidence in [0.0, 1.0] from absolute imbalance strength."""
    total = bid_size + ask_size
    if total <= 0:
        return 0.0
    return abs(bid_size - ask_size) / total
