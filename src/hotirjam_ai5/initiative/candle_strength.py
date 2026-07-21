"""IN03 — Candle Strength Analyzer.

Evaluates recent candle quality from body size, consistency, close strength,
and consecutive direction. No indicators. No AI.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative.initiative_models import (
    CandleStrengthResult,
    ImpulseSide,
    OhlcCandle,
)

_WINDOW = 5


def _finite_candle(c: OhlcCandle) -> bool:
    return all(math.isfinite(v) for v in (c.open, c.high, c.low, c.close)) and c.high >= c.low


def _body(c: OhlcCandle) -> float:
    return abs(c.close - c.open)


def _range(c: OhlcCandle) -> float:
    return max(c.high - c.low, 0.0)


def _close_strength(c: OhlcCandle) -> float:
    """0–1: how strongly the candle closed in its body direction."""
    rng = _range(c)
    if rng <= 0.0:
        return 0.0
    if c.close >= c.open:
        return (c.close - c.low) / rng
    return (c.high - c.close) / rng


def analyze_candle_strength(candles: Sequence[OhlcCandle]) -> CandleStrengthResult:
    """Score candle quality over the recent window."""
    valid = [c for c in candles if _finite_candle(c)]
    if not valid:
        return CandleStrengthResult(0.0, ImpulseSide.NONE, ("No valid candles",))

    window = valid[-_WINDOW:]
    n = len(window)

    # Body size: average body / average range.
    bodies = [_body(c) for c in window]
    ranges = [_range(c) for c in window]
    avg_body = sum(bodies) / n
    avg_range = sum(ranges) / n
    body_ratio = (avg_body / avg_range) if avg_range > 0.0 else 0.0
    body_score = min(100.0, body_ratio * 100.0)

    bullish = sum(1 for c in window if c.close > c.open)
    bearish = sum(1 for c in window if c.close < c.open)
    if bullish > bearish:
        direction = ImpulseSide.BUY
        consistency = bullish / n
    elif bearish > bullish:
        direction = ImpulseSide.SELL
        consistency = bearish / n
    else:
        direction = ImpulseSide.NONE
        consistency = 0.5
    consistency_score = consistency * 100.0

    close_score = (sum(_close_strength(c) for c in window) / n) * 100.0

    # Consecutive direction streak ending at latest candle.
    streak = 1
    for i in range(len(window) - 1, 0, -1):
        prev = window[i - 1]
        cur = window[i]
        prev_up = prev.close > prev.open
        cur_up = cur.close > cur.open
        prev_down = prev.close < prev.open
        cur_down = cur.close < cur.open
        if (prev_up and cur_up) or (prev_down and cur_down):
            streak += 1
        else:
            break
    streak_score = min(100.0, (streak / max(n, 1)) * 100.0)

    score = (
        0.30 * body_score
        + 0.30 * consistency_score
        + 0.25 * close_score
        + 0.15 * streak_score
    )
    score = max(0.0, min(100.0, score))

    reasons = (
        f"Body ratio {body_ratio:.2f}",
        f"Directional consistency {consistency:.2f}",
        f"Close strength {close_score:.1f}",
        f"Consecutive streak {streak}",
    )
    return CandleStrengthResult(score, direction, reasons)
