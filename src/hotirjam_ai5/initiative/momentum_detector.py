"""IN02 — Momentum Detector.

Measures whether market momentum is accelerating from raw price movement.
No indicators. No AI.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative.initiative_models import (
    ImpulseSide,
    MomentumResult,
    MomentumState,
    OhlcCandle,
)

_WINDOW = 6


def _finite_candle(c: OhlcCandle) -> bool:
    return all(math.isfinite(v) for v in (c.open, c.high, c.low, c.close))


def detect_momentum(
    candles: Sequence[OhlcCandle],
    *,
    tick_size: float,
) -> MomentumResult:
    """Compare early vs late velocity in the recent window."""
    if tick_size <= 0.0 or not math.isfinite(tick_size):
        return MomentumResult(0.0, MomentumState.LOW, ImpulseSide.NONE, ("Invalid tick size",))

    valid = [c for c in candles if _finite_candle(c)]
    if len(valid) < 4:
        return MomentumResult(
            0.0,
            MomentumState.LOW,
            ImpulseSide.NONE,
            ("Insufficient candles for momentum",),
        )

    window = valid[-_WINDOW:]
    mid = len(window) // 2
    early = window[:mid]
    late = window[mid:]
    if len(early) < 2 or len(late) < 2:
        return MomentumResult(
            0.0,
            MomentumState.LOW,
            ImpulseSide.NONE,
            ("Insufficient candles for momentum",),
        )

    early_vel = (early[-1].close - early[0].close) / (tick_size * max(1, len(early) - 1))
    late_vel = (late[-1].close - late[0].close) / (tick_size * max(1, len(late) - 1))
    accel = late_vel - early_vel

    # Magnitude of late velocity + acceleration contribution.
    speed = abs(late_vel)
    accel_mag = abs(accel)
    # 2 ticks/bar speed ≈ 50; 2 ticks/bar^2 accel ≈ 50.
    score = min(100.0, (speed / 2.0) * 50.0 + (accel_mag / 2.0) * 50.0)

    if late_vel > 0.05:
        direction = ImpulseSide.BUY
    elif late_vel < -0.05:
        direction = ImpulseSide.SELL
    else:
        direction = ImpulseSide.NONE

    if score < 30.0:
        state = MomentumState.LOW
    elif score < 65.0:
        state = MomentumState.MEDIUM
    else:
        state = MomentumState.HIGH

    reasons = (
        f"Late velocity {late_vel:.2f} ticks/bar",
        f"Acceleration {accel:.2f}",
        f"Momentum state {state.value}",
    )
    return MomentumResult(score, state, direction, reasons)
