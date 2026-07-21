"""Continuation Engine — initiative continuing or fading (Module 04).

Independent. Not wired to Decision, broker, or trading logic.
Does not modify Objective, Initiative, or Response engines.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from hotirjam_ai5.continuation.continuation_models import ContinuationInputs
from hotirjam_ai5.continuation.continuation_scorer import score_continuation
from hotirjam_ai5.continuation.continuation_snapshot import ContinuationSnapshot
from hotirjam_ai5.continuation.continuation_strength import measure_continuation_strength
from hotirjam_ai5.continuation.momentum_decay import measure_momentum_decay
from hotirjam_ai5.continuation.pressure_persistence import measure_pressure_persistence


def evaluate_continuation(inputs: ContinuationInputs) -> ContinuationSnapshot:
    """Run CT01→CT04 and return a ContinuationSnapshot.

    Pure function of inputs. Deterministic for identical data.
    """
    if not math.isfinite(inputs.tick_size) or inputs.tick_size <= 0.0:
        return ContinuationSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Invalid tick size",
        )
    if not inputs.candles:
        return ContinuationSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Empty candle input",
        )

    pressure = measure_pressure_persistence(
        inputs.candles,
        initiative=inputs.initiative,
        response=inputs.response,
        tick_size=inputs.tick_size,
    )
    decay = measure_momentum_decay(
        inputs.candles,
        initiative=inputs.initiative,
        tick_size=inputs.tick_size,
    )
    strength = measure_continuation_strength(
        inputs.candles,
        initiative=inputs.initiative,
    )
    return score_continuation(
        initiative=inputs.initiative,
        pressure=pressure,
        decay=decay,
        strength=strength,
        objectives=inputs.objectives,
        timestamp=inputs.timestamp,
    )


class ContinuationEngine:
    """Stateful wrapper retaining the latest ContinuationSnapshot."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = ContinuationSnapshot.empty(timestamp=self._clock())

    def evaluate(self, inputs: ContinuationInputs) -> ContinuationSnapshot:
        self._latest = evaluate_continuation(inputs)
        return self._latest

    def snapshot(self) -> ContinuationSnapshot:
        return self._latest
