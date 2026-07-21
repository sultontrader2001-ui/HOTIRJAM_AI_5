"""Objective Engine V2 — nearest eligible structural High / Low.

Deterministic. No indicators, no AI, no broker, no trade decisions.
Does not predict. Does not trade. Describes the battlefield only.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence

from hotirjam_ai5.objective.objective_models import ConfirmedSwing, ObjectiveInputs
from hotirjam_ai5.objective.objective_snapshot import ObjectiveSnapshot
from hotirjam_ai5.objective_diagnostics.models import (
    CandidateCategory,
    LifecycleState,
    ObjectiveDiagnosticsInputs,
    SwingDiagnostic,
    SwingSide,
)
from hotirjam_ai5.objective_diagnostics.objective_audit import audit_objectives


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


def _pick_nearest_eligible(
    candidates: Sequence[SwingDiagnostic],
    *,
    side: SwingSide,
    current_price: float,
) -> SwingDiagnostic | None:
    """Select the nearest eligible MAJOR+ACTIVE structural candidate.

    Tie-break (deterministic):
    1. Higher strength
    2. Later ``confirmed_at`` (missing treated as -inf)
    3. Lower price (stable, direction-agnostic)
    """
    eligible = [
        candidate
        for candidate in candidates
        if candidate.eligible
        and candidate.lifecycle is LifecycleState.ACTIVE
        and candidate.category is CandidateCategory.MAJOR
        and candidate.side is side
        and (
            (side is SwingSide.HIGH and candidate.price > current_price)
            or (side is SwingSide.LOW and candidate.price < current_price)
        )
    ]
    if not eligible:
        return None

    def sort_key(candidate: SwingDiagnostic) -> tuple[float, float, float, float]:
        confirmed = (
            candidate.confirmed_at
            if candidate.confirmed_at is not None
            else float("-inf")
        )
        # Ascending distance; descending strength/time → negate those.
        return (
            candidate.distance_ticks,
            -candidate.current_strength,
            -confirmed,
            candidate.price,
        )

    return min(eligible, key=sort_key)


def evaluate_objectives(inputs: ObjectiveInputs) -> ObjectiveSnapshot:
    """Compute nearest eligible structural high and low from ``inputs``.

    Rules:
    - Classify confirmed swings using the shared structural audit
    - Keep only Eligible + ACTIVE + MAJOR candidates on the correct price side
    - Select the nearest remaining High and Low independently
    - Never fall back to MICRO, MINOR, ineligible, or merely-nearest swings
    - Trade direction is ignored — both sides are always evaluated
    - No eligible candidate yields ``None`` fields for that side
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

    valid_highs = tuple(s for s in inputs.confirmed_highs if _is_valid_swing(s))
    valid_lows = tuple(s for s in inputs.confirmed_lows if _is_valid_swing(s))
    report = audit_objectives(
        ObjectiveDiagnosticsInputs(
            current_price=inputs.current_price,
            tick_size=inputs.tick_size,
            confirmed_highs=valid_highs,
            confirmed_lows=valid_lows,
            timestamp=inputs.timestamp,
        )
    )

    high_pick = _pick_nearest_eligible(
        report.highs,
        side=SwingSide.HIGH,
        current_price=inputs.current_price,
    )
    low_pick = _pick_nearest_eligible(
        report.lows,
        side=SwingSide.LOW,
        current_price=inputs.current_price,
    )

    return ObjectiveSnapshot(
        nearest_high_price=high_pick.price if high_pick else None,
        nearest_high_distance_ticks=high_pick.distance_ticks if high_pick else None,
        nearest_high_strength=high_pick.current_strength if high_pick else None,
        nearest_low_price=low_pick.price if low_pick else None,
        nearest_low_distance_ticks=low_pick.distance_ticks if low_pick else None,
        nearest_low_strength=low_pick.current_strength if low_pick else None,
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
