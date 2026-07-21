"""Response Engine — opposing-side reaction after initiative (Module 03).

Independent. Not wired to Decision, broker, or trading logic.
Does not modify Objective or Initiative engines.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from hotirjam_ai5.response.counter_move_detector import detect_counter_move
from hotirjam_ai5.response.initiative_preservation import evaluate_initiative_preservation
from hotirjam_ai5.response.response_models import ResponseInputs
from hotirjam_ai5.response.response_scorer import score_response
from hotirjam_ai5.response.response_snapshot import ResponseSnapshot
from hotirjam_ai5.response.response_strength import analyze_response_strength


def evaluate_response(inputs: ResponseInputs) -> ResponseSnapshot:
    """Run RE01→RE04 and return a ResponseSnapshot.

    Pure function of inputs. Deterministic for identical data.
    """
    if not math.isfinite(inputs.tick_size) or inputs.tick_size <= 0.0:
        return ResponseSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Invalid tick size",
        )
    if not inputs.candles:
        return ResponseSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Empty candle input",
        )

    counter = detect_counter_move(
        inputs.candles,
        initiative=inputs.initiative,
        tick_size=inputs.tick_size,
    )
    strength = analyze_response_strength(
        inputs.candles,
        initiative=inputs.initiative,
        counter=counter,
        tick_size=inputs.tick_size,
    )
    preservation = evaluate_initiative_preservation(
        initiative=inputs.initiative,
        counter=counter,
        strength=strength,
    )
    return score_response(
        counter=counter,
        strength=strength,
        preservation=preservation,
        objectives=inputs.objectives,
        timestamp=inputs.timestamp,
    )


class ResponseEngine:
    """Stateful wrapper retaining the latest ResponseSnapshot."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = ResponseSnapshot.empty(timestamp=self._clock())

    def evaluate(self, inputs: ResponseInputs) -> ResponseSnapshot:
        self._latest = evaluate_response(inputs)
        return self._latest

    def snapshot(self) -> ResponseSnapshot:
        return self._latest
