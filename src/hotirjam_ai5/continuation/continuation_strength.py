"""CT03 — Continuation Strength.

Measures whether recent candles continue supporting the initiative side.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot, OhlcCandle
from hotirjam_ai5.continuation.continuation_models import ContinuationStrengthResult

_WINDOW = 5


def _finite(c: OhlcCandle) -> bool:
    return all(math.isfinite(v) for v in (c.open, c.high, c.low, c.close)) and c.high >= c.low


def measure_continuation_strength(
    candles: Sequence[OhlcCandle],
    *,
    initiative: InitiativeSnapshot,
) -> ContinuationStrengthResult:
    """Score candle support for the initiative direction (0–100)."""
    if initiative.initiative_side is InitiativeSide.NONE:
        return ContinuationStrengthResult(0.0, ("No initiative — no continuation strength",))

    valid = [c for c in candles if _finite(c)]
    if not valid:
        return ContinuationStrengthResult(0.0, ("No valid candles",))

    window = valid[-_WINDOW:]
    n = len(window)

    if initiative.initiative_side is InitiativeSide.BUYER:
        supporting = [c for c in window if c.close > c.open]
        close_scores = [
            ((c.close - c.low) / (c.high - c.low)) if (c.high - c.low) > 0 else 0.0
            for c in window
        ]
    else:
        supporting = [c for c in window if c.close < c.open]
        close_scores = [
            ((c.high - c.close) / (c.high - c.low)) if (c.high - c.low) > 0 else 0.0
            for c in window
        ]

    support_ratio = len(supporting) / n
    close_strength = sum(close_scores) / n

    # Consecutive supporting streak from the end.
    streak = 0
    for c in reversed(window):
        if initiative.initiative_side is InitiativeSide.BUYER and c.close > c.open:
            streak += 1
        elif initiative.initiative_side is InitiativeSide.SELLER and c.close < c.open:
            streak += 1
        else:
            break
    streak_score = (streak / n) * 100.0

    bodies = [abs(c.close - c.open) for c in supporting] if supporting else [0.0]
    ranges = [max(c.high - c.low, 0.0) for c in supporting] if supporting else [1.0]
    avg_body = sum(bodies) / len(bodies)
    avg_range = sum(ranges) / len(ranges)
    body_ratio = (avg_body / avg_range) if avg_range > 0 else 0.0

    score = (
        0.35 * support_ratio * 100.0
        + 0.30 * close_strength * 100.0
        + 0.20 * streak_score
        + 0.15 * min(100.0, body_ratio * 100.0)
    )
    score = max(0.0, min(100.0, score))

    reasons = (
        f"Supporting candles {len(supporting)}/{n}",
        f"Close strength {close_strength:.2f}",
        f"Supporting streak {streak}",
        f"Continuation strength {score:.1f}",
    )
    return ContinuationStrengthResult(score, reasons)
