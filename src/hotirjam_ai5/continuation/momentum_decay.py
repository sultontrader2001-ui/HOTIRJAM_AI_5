"""CT02 — Momentum Decay.

Measures whether momentum is weakening (high decay) or strengthening (low decay).
``momentum_decay`` is 0–100 where higher means more fade.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot, OhlcCandle
from hotirjam_ai5.continuation.continuation_models import MomentumDecayResult

_WINDOW = 6


def _finite(c: OhlcCandle) -> bool:
    return all(math.isfinite(v) for v in (c.open, c.high, c.low, c.close))


def measure_momentum_decay(
    candles: Sequence[OhlcCandle],
    *,
    initiative: InitiativeSnapshot,
    tick_size: float,
) -> MomentumDecayResult:
    """Compare early vs late velocity aligned to initiative; score decay."""
    if tick_size <= 0.0 or not math.isfinite(tick_size):
        return MomentumDecayResult(100.0, ("Invalid tick size — full decay",))

    if initiative.initiative_side is InitiativeSide.NONE:
        return MomentumDecayResult(0.0, ("No initiative — decay not applicable",))

    valid = [c for c in candles if _finite(c)]
    if len(valid) < 4:
        return MomentumDecayResult(100.0, ("Insufficient candles — treat as decayed",))

    window = valid[-_WINDOW:]
    mid = len(window) // 2
    early, late = window[:mid], window[mid:]
    if len(early) < 2 or len(late) < 2:
        return MomentumDecayResult(100.0, ("Insufficient candles — treat as decayed",))

    early_vel = (early[-1].close - early[0].close) / (tick_size * max(1, len(early) - 1))
    late_vel = (late[-1].close - late[0].close) / (tick_size * max(1, len(late) - 1))

    if initiative.initiative_side is InitiativeSide.BUYER:
        early_aligned = early_vel
        late_aligned = late_vel
    else:
        early_aligned = -early_vel
        late_aligned = -late_vel

    # Decay: late weaker than early (or late opposing).
    if early_aligned <= 0.05 and late_aligned <= 0.05:
        decay = 80.0
        note = "Little aligned momentum throughout"
    elif late_aligned >= early_aligned and late_aligned > 0.05:
        # Accelerating or holding — low decay.
        ratio = late_aligned / max(early_aligned, 0.05)
        decay = max(0.0, min(40.0, 40.0 - (ratio - 1.0) * 20.0))
        note = f"Momentum holding/strengthening (late/early={ratio:.2f})"
    else:
        # Weakening.
        drop = early_aligned - late_aligned
        decay = min(100.0, 40.0 + (drop / max(abs(early_aligned), 0.1)) * 60.0)
        note = f"Momentum fading (drop={drop:.2f})"

    decay = max(0.0, min(100.0, decay))
    reasons = (
        f"Early aligned vel {early_aligned:.2f}",
        f"Late aligned vel {late_aligned:.2f}",
        note,
        f"Momentum decay {decay:.1f}",
    )
    return MomentumDecayResult(decay, reasons)
