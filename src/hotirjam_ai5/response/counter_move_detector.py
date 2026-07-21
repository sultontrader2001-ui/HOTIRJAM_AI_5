"""RE01 — Counter Move Detector.

Detects whether the side opposite to initiative attempted a response.
Pure price analysis. No trade decisions.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot, OhlcCandle
from hotirjam_ai5.response.response_models import CounterMoveResult, ResponseSide

_WINDOW = 4
_MIN_COUNTER_TICKS = 1.5


def _finite(c: OhlcCandle) -> bool:
    return all(math.isfinite(v) for v in (c.open, c.high, c.low, c.close, c.volume))


def _opposing_side(initiative: InitiativeSide) -> ResponseSide:
    if initiative is InitiativeSide.BUYER:
        return ResponseSide.SELLER
    if initiative is InitiativeSide.SELLER:
        return ResponseSide.BUYER
    return ResponseSide.NONE


def detect_counter_move(
    candles: Sequence[OhlcCandle],
    *,
    initiative: InitiativeSnapshot,
    tick_size: float,
) -> CounterMoveResult:
    """Detect a counter move against the current initiative side."""
    if tick_size <= 0.0 or not math.isfinite(tick_size):
        return CounterMoveResult(False, ResponseSide.NONE, 0.0, ("Invalid tick size",))

    if initiative.initiative_side is InitiativeSide.NONE:
        return CounterMoveResult(
            False,
            ResponseSide.NONE,
            0.0,
            ("No initiative — counter-response not applicable",),
        )

    valid = [c for c in candles if _finite(c) and c.high >= c.low]
    if len(valid) < 2:
        return CounterMoveResult(
            False,
            ResponseSide.NONE,
            0.0,
            ("Insufficient candles for counter-move detection",),
        )

    opposing = _opposing_side(initiative.initiative_side)
    window = valid[-_WINDOW:]
    first = window[0]
    last = window[-1]
    net_ticks = (last.close - first.close) / tick_size

    # Counter direction: against BUYER initiative → net down; against SELLER → net up.
    if opposing is ResponseSide.SELLER:
        counter_ticks = max(0.0, -net_ticks)
        body_hits = sum(1 for c in window if c.close < c.open)
    else:
        counter_ticks = max(0.0, net_ticks)
        body_hits = sum(1 for c in window if c.close > c.open)

    reasons: list[str] = [
        f"Initiative {initiative.initiative_side.value}",
        f"Expected counter {opposing.value}",
        f"Counter displacement {counter_ticks:.1f} ticks",
        f"Counter bodies {body_hits}/{len(window)}",
    ]

    if counter_ticks < _MIN_COUNTER_TICKS and body_hits < max(1, len(window) // 2):
        reasons.append("No meaningful counter move detected")
        return CounterMoveResult(False, ResponseSide.NONE, counter_ticks, tuple(reasons))

    reasons.append("Counter move detected")
    return CounterMoveResult(True, opposing, counter_ticks, tuple(reasons))
