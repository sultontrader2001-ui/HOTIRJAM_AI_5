"""Initiative Engine — market initiative observation (Module 02).

Independent. Not wired to Decision, broker, or trading logic.
Does not modify or depend on Objective Engine internals beyond ObjectiveSnapshot.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from hotirjam_ai5.initiative.candle_strength import analyze_candle_strength
from hotirjam_ai5.initiative.impulse_detector import detect_impulse
from hotirjam_ai5.initiative.initiative_models import InitiativeInputs
from hotirjam_ai5.initiative.initiative_scorer import score_initiative
from hotirjam_ai5.initiative.initiative_snapshot import InitiativeSnapshot
from hotirjam_ai5.initiative.momentum_detector import detect_momentum


def evaluate_initiative(inputs: InitiativeInputs) -> InitiativeSnapshot:
    """Run IN01→IN04 and return an InitiativeSnapshot.

    Pure function of inputs. Deterministic for identical candles/tick_size.
    """
    if not math.isfinite(inputs.tick_size) or inputs.tick_size <= 0.0:
        return InitiativeSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Invalid tick size",
        )
    if not inputs.candles:
        return InitiativeSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Empty candle input",
        )

    impulse = detect_impulse(inputs.candles, tick_size=inputs.tick_size)
    momentum = detect_momentum(inputs.candles, tick_size=inputs.tick_size)
    candles = analyze_candle_strength(inputs.candles)
    return score_initiative(
        impulse=impulse,
        momentum=momentum,
        candles=candles,
        objectives=inputs.objectives,
        timestamp=inputs.timestamp,
    )


class InitiativeEngine:
    """Stateful wrapper retaining the latest InitiativeSnapshot."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = InitiativeSnapshot.empty(timestamp=self._clock())

    def evaluate(self, inputs: InitiativeInputs) -> InitiativeSnapshot:
        self._latest = evaluate_initiative(inputs)
        return self._latest

    def snapshot(self) -> InitiativeSnapshot:
        return self._latest
