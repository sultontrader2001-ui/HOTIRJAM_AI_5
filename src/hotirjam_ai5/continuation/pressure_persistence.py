"""CT01 — Pressure Persistence.

Measures whether directional pressure is still maintained in the initiative direction.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot, OhlcCandle
from hotirjam_ai5.response import ResponseSnapshot, ResponseState
from hotirjam_ai5.continuation.continuation_models import PressurePersistenceResult

_WINDOW = 5


def _finite(c: OhlcCandle) -> bool:
    return all(math.isfinite(v) for v in (c.open, c.high, c.low, c.close, c.volume))


def measure_pressure_persistence(
    candles: Sequence[OhlcCandle],
    *,
    initiative: InitiativeSnapshot,
    response: ResponseSnapshot,
    tick_size: float,
) -> PressurePersistenceResult:
    """Score remaining directional pressure (0–100)."""
    if tick_size <= 0.0 or not math.isfinite(tick_size):
        return PressurePersistenceResult(0.0, ("Invalid tick size",))

    if initiative.initiative_side is InitiativeSide.NONE:
        return PressurePersistenceResult(0.0, ("No initiative — no pressure to persist",))

    valid = [c for c in candles if _finite(c) and c.high >= c.low]
    if len(valid) < 2:
        return PressurePersistenceResult(0.0, ("Insufficient candles for pressure",))

    window = valid[-_WINDOW:]
    first, last = window[0], window[-1]
    net_ticks = (last.close - first.close) / tick_size

    if initiative.initiative_side is InitiativeSide.BUYER:
        aligned_ticks = max(0.0, net_ticks)
        aligned_bodies = sum(1 for c in window if c.close > c.open)
    else:
        aligned_ticks = max(0.0, -net_ticks)
        aligned_bodies = sum(1 for c in window if c.close < c.open)

    body_ratio = aligned_bodies / len(window)
    # 12 ticks of aligned displacement ≈ full displacement contribution.
    disp_score = min(100.0, (aligned_ticks / 12.0) * 100.0)
    body_score = body_ratio * 100.0

    # Response penalty: strong opposing response reduces pressure.
    if not response.initiative_preserved:
        response_factor = 0.45
        response_note = "Initiative not preserved — pressure discounted"
    elif response.response_state is ResponseState.STRONG:
        response_factor = 0.65
        response_note = "Strong response — pressure discounted"
    elif response.response_state is ResponseState.FAILED:
        response_factor = 1.0
        response_note = "Failed response — pressure intact"
    else:
        response_factor = 0.85
        response_note = f"Response {response.response_state.value} — mild pressure discount"

    # Blend with initiative score as a prior.
    base = 0.45 * disp_score + 0.35 * body_score + 0.20 * initiative.initiative_score
    pressure = max(0.0, min(100.0, base * response_factor))

    reasons = (
        f"Aligned displacement {aligned_ticks:.1f} ticks",
        f"Aligned bodies {aligned_bodies}/{len(window)}",
        response_note,
        f"Pressure score {pressure:.1f}",
    )
    return PressurePersistenceResult(pressure, reasons)
