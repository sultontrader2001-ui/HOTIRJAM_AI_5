"""IN01 — Impulse Detector.

Detects whether a directional impulse has started from raw price movement.
No indicators. No AI. Not a trade decision.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative.initiative_models import (
    ImpulseResult,
    ImpulseSide,
    OhlcCandle,
)

# Minimum net displacement (ticks) to call an impulse.
_MIN_IMPULSE_TICKS = 2.0
# Lookback candles for impulse window (use last N when more available).
_WINDOW = 5


def _finite_candle(c: OhlcCandle) -> bool:
    return all(
        math.isfinite(v)
        for v in (c.open, c.high, c.low, c.close, c.volume)
    )


def detect_impulse(
    candles: Sequence[OhlcCandle],
    *,
    tick_size: float,
) -> ImpulseResult:
    """Detect directional impulse from recent OHLC bars.

    Uses net close-to-close displacement and body direction majority.
    """
    if tick_size <= 0.0 or not math.isfinite(tick_size):
        return ImpulseResult(ImpulseSide.NONE, 0.0, ("Invalid tick size",))

    valid = [c for c in candles if _finite_candle(c) and c.high >= c.low]
    if len(valid) < 2:
        return ImpulseResult(ImpulseSide.NONE, 0.0, ("Insufficient candles for impulse",))

    window = valid[-_WINDOW:]
    first = window[0]
    last = window[-1]
    net_ticks = (last.close - first.close) / tick_size
    abs_net = abs(net_ticks)

    bullish = 0
    bearish = 0
    for c in window:
        body = c.close - c.open
        if body > 0:
            bullish += 1
        elif body < 0:
            bearish += 1

    reasons: list[str] = []
    if abs_net < _MIN_IMPULSE_TICKS:
        reasons.append(f"Net move {abs_net:.1f} ticks below impulse threshold")
        return ImpulseResult(ImpulseSide.NONE, 0.0, tuple(reasons))

    # Score: scale net displacement; 20 ticks ≈ full score.
    score = min(100.0, (abs_net / 20.0) * 100.0)

    if net_ticks > 0 and bullish >= bearish:
        reasons.append(f"Upward impulse {abs_net:.1f} ticks")
        reasons.append(f"Bullish bodies {bullish}/{len(window)}")
        return ImpulseResult(ImpulseSide.BUY, score, tuple(reasons))

    if net_ticks < 0 and bearish >= bullish:
        reasons.append(f"Downward impulse {abs_net:.1f} ticks")
        reasons.append(f"Bearish bodies {bearish}/{len(window)}")
        return ImpulseResult(ImpulseSide.SELL, score, tuple(reasons))

    reasons.append("Displacement and body majority disagree")
    # Weak conflicting impulse — half score, no side.
    return ImpulseResult(ImpulseSide.NONE, score * 0.25, tuple(reasons))
