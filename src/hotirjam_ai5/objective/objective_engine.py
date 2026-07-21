"""Objective Engine — nearest confirmed Swing High / Swing Low.

Deterministic. No indicators, no AI, no broker, no trade decisions.
Does not predict. Does not trade. Describes the battlefield only.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence

from hotirjam_ai5.objective.objective_models import ConfirmedSwing, ObjectiveInputs
from hotirjam_ai5.objective.objective_snapshot import ObjectiveSnapshot


def _is_finite(value: float) -> bool:
    return math.isfinite(value)


def _is_valid_swing(swing: ConfirmedSwing) -> bool:
    """Reject non-finite prices / strengths and out-of-range strength."""
    if not _is_finite(swing.price):
        return False
    if not _is_finite(swing.strength):
        return False
    if swing.strength < 0.0 or swing.strength > 100.0:
        return False
    return True


def _distance_ticks(price: float, current_price: float, tick_size: float) -> float:
    return abs(price - current_price) / tick_size


def _pick_nearest(
    candidates: Sequence[ConfirmedSwing],
    *,
    current_price: float,
    tick_size: float,
) -> tuple[ConfirmedSwing, float] | None:
    """Select the nearest swing by tick distance.

    Tie-break (deterministic):
    1. Higher strength
    2. Later ``confirmed_at`` (missing treated as -inf)
    3. Lower price (stable, direction-agnostic)
    """
    if not candidates:
        return None

    def sort_key(swing: ConfirmedSwing) -> tuple[float, float, float, float]:
        dist = _distance_ticks(swing.price, current_price, tick_size)
        confirmed = swing.confirmed_at if swing.confirmed_at is not None else float("-inf")
        # Ascending distance; descending strength/time → negate those.
        return (dist, -swing.strength, -confirmed, swing.price)

    best = min(candidates, key=sort_key)
    return best, _distance_ticks(best.price, current_price, tick_size)


def evaluate_objectives(inputs: ObjectiveInputs) -> ObjectiveSnapshot:
    """Compute nearest confirmed high and low from ``inputs``.

    Rules:
    - Nearest High: closest valid confirmed swing high **above** current price
    - Nearest Low: closest valid confirmed swing low **below** current price
    - Trade direction is ignored — both sides are always evaluated
    - Invalid / empty swings yield ``None`` fields for that side
    """
    if not _is_finite(inputs.current_price) or not _is_finite(inputs.tick_size):
        return ObjectiveSnapshot.empty(
            timestamp=inputs.timestamp,
            current_price=None,
        )
    if inputs.tick_size <= 0.0:
        return ObjectiveSnapshot.empty(
            timestamp=inputs.timestamp,
            current_price=inputs.current_price,
        )

    valid_highs = [
        s
        for s in inputs.confirmed_highs
        if _is_valid_swing(s) and s.price > inputs.current_price
    ]
    valid_lows = [
        s
        for s in inputs.confirmed_lows
        if _is_valid_swing(s) and s.price < inputs.current_price
    ]

    high_pick = _pick_nearest(
        valid_highs,
        current_price=inputs.current_price,
        tick_size=inputs.tick_size,
    )
    low_pick = _pick_nearest(
        valid_lows,
        current_price=inputs.current_price,
        tick_size=inputs.tick_size,
    )

    return ObjectiveSnapshot(
        nearest_high_price=high_pick[0].price if high_pick else None,
        nearest_high_distance_ticks=high_pick[1] if high_pick else None,
        nearest_high_strength=high_pick[0].strength if high_pick else None,
        nearest_low_price=low_pick[0].price if low_pick else None,
        nearest_low_distance_ticks=low_pick[1] if low_pick else None,
        nearest_low_strength=low_pick[0].strength if low_pick else None,
        current_price=inputs.current_price,
        timestamp=inputs.timestamp,
    )


class ObjectiveEngine:
    """Stateful wrapper that stores the latest ObjectiveSnapshot.

    Evaluation itself is a pure function of the supplied inputs.
    Not connected to Decision, broker, or execution pipelines.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = ObjectiveSnapshot.empty(timestamp=self._clock())

    def evaluate(self, inputs: ObjectiveInputs) -> ObjectiveSnapshot:
        """Evaluate objectives and retain the result."""
        self._latest = evaluate_objectives(inputs)
        return self._latest

    def snapshot(self) -> ObjectiveSnapshot:
        """Return the latest snapshot without re-evaluating."""
        return self._latest
