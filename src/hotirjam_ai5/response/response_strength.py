"""RE02 — Response Strength Analyzer.

Measures quality of the opposing side's counter-response.
Uses body quality, volume emphasis, and retracement depth.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot, OhlcCandle
from hotirjam_ai5.response.response_models import CounterMoveResult, ResponseSide, ResponseStrengthResult

_WINDOW = 4


def _finite(c: OhlcCandle) -> bool:
    return all(math.isfinite(v) for v in (c.open, c.high, c.low, c.close, c.volume))


def analyze_response_strength(
    candles: Sequence[OhlcCandle],
    *,
    initiative: InitiativeSnapshot,
    counter: CounterMoveResult,
    tick_size: float,
) -> ResponseStrengthResult:
    """Score how strong the counter-response is (0–100)."""
    if not counter.detected or counter.response_side is ResponseSide.NONE:
        return ResponseStrengthResult(0.0, ("No counter move to score",))

    if tick_size <= 0.0 or not math.isfinite(tick_size):
        return ResponseStrengthResult(0.0, ("Invalid tick size",))

    valid = [c for c in candles if _finite(c) and c.high >= c.low]
    if not valid:
        return ResponseStrengthResult(0.0, ("No valid candles",))

    window = valid[-_WINDOW:]
    n = len(window)

    # Body quality in counter direction.
    if counter.response_side is ResponseSide.SELLER:
        directed = [c for c in window if c.close < c.open]
    else:
        directed = [c for c in window if c.close > c.open]

    body_ratios: list[float] = []
    for c in directed:
        rng = c.high - c.low
        if rng > 0.0:
            body_ratios.append(abs(c.close - c.open) / rng)
    body_score = (sum(body_ratios) / len(body_ratios) * 100.0) if body_ratios else 0.0

    # Volume emphasis on counter candles vs window average.
    avg_vol = sum(max(0.0, c.volume) for c in window) / n
    if avg_vol > 0.0 and directed:
        counter_vol = sum(max(0.0, c.volume) for c in directed) / len(directed)
        vol_ratio = counter_vol / avg_vol
        volume_score = min(100.0, vol_ratio * 50.0)
    else:
        volume_score = 30.0  # neutral when volume absent

    # Magnitude vs initiative score (stronger counter relative to initiative = higher).
    initiative_ref = max(initiative.initiative_score, 1.0)
    # 20 ticks of counter ≈ full magnitude contribution.
    mag_score = min(100.0, (counter.magnitude_ticks / 20.0) * 100.0)
    relative = min(100.0, (counter.magnitude_ticks / (initiative_ref / 5.0)) * 50.0)

    strength = 0.35 * body_score + 0.20 * volume_score + 0.30 * mag_score + 0.15 * relative
    strength = max(0.0, min(100.0, strength))

    reasons = (
        f"Counter bodies {len(directed)}/{n}",
        f"Body quality {body_score:.1f}",
        f"Volume score {volume_score:.1f}",
        f"Magnitude score {mag_score:.1f}",
        f"Relative to initiative {relative:.1f}",
    )
    # Silence unused initiative_side branch hint for completeness in reasons.
    if initiative.initiative_side is not InitiativeSide.NONE:
        reasons = reasons + (f"Against {initiative.initiative_side.value} initiative",)
    return ResponseStrengthResult(strength, reasons)
