"""Objective Engine V2 — nearest eligible structural High / Low.

Deterministic. No indicators, no AI, no broker, no trade decisions.
Does not predict. Does not trade. Describes the battlefield only.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hotirjam_ai5.objective.objective_models import ConfirmedSwing, ObjectiveInputs
from hotirjam_ai5.objective.objective_snapshot import (
    ObjectivePersistenceState,
    ObjectiveSnapshot,
)
from hotirjam_ai5.objective_diagnostics.models import (
    CandidateCategory,
    LifecycleState,
    ObjectiveAuditReport,
    ObjectiveDiagnosticsInputs,
    SwingDiagnostic,
    SwingSide,
)
from hotirjam_ai5.objective_diagnostics.objective_audit import audit_objectives
from hotirjam_ai5.objective_diagnostics.persistent_hierarchy import (
    PersistentStructuralHierarchy,
    active_structural_hierarchy,
    use_structural_hierarchy,
)


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
        and candidate.lifecycle
        in {
            LifecycleState.NEW,
            LifecycleState.ACTIVE,
            LifecycleState.CHALLENGED,
        }
        and candidate.category is CandidateCategory.MAJOR
        and candidate.side is side
        and (
            candidate.lifecycle is LifecycleState.CHALLENGED
            or
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


def _evaluate_structural_candidates(
    inputs: ObjectiveInputs,
) -> tuple[
    ObjectiveSnapshot,
    ObjectiveAuditReport | None,
    SwingDiagnostic | None,
    SwingDiagnostic | None,
]:
    """Classify and select current candidates without persistence."""
    if not _is_finite(inputs.current_price) or not _is_finite(inputs.tick_size):
        return (
            ObjectiveSnapshot.empty(timestamp=inputs.timestamp, current_price=None),
            None,
            None,
            None,
        )
    if inputs.tick_size <= 0.0:
        return (
            ObjectiveSnapshot.empty(
                timestamp=inputs.timestamp,
                current_price=inputs.current_price,
            ),
            None,
            None,
            None,
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

    snapshot = ObjectiveSnapshot(
        nearest_high_price=high_pick.price if high_pick else None,
        nearest_high_distance_ticks=high_pick.distance_ticks if high_pick else None,
        nearest_high_strength=high_pick.current_strength if high_pick else None,
        nearest_low_price=low_pick.price if low_pick else None,
        nearest_low_distance_ticks=low_pick.distance_ticks if low_pick else None,
        nearest_low_strength=low_pick.current_strength if low_pick else None,
        current_price=inputs.current_price,
        timestamp=inputs.timestamp,
        high_state=ObjectivePersistenceState.NEW if high_pick else None,
        low_state=ObjectivePersistenceState.NEW if low_pick else None,
    )
    return snapshot, report, high_pick, low_pick


def evaluate_objectives(inputs: ObjectiveInputs) -> ObjectiveSnapshot:
    """Compute current eligible structural high and low from ``inputs``.

    Rules:
    - Classify confirmed swings using the shared structural audit
    - Keep only Eligible + ACTIVE + MAJOR candidates on the correct price side
    - Select the nearest remaining High and Low independently
    - Never fall back to MICRO, MINOR, ineligible, or merely-nearest swings
    - Trade direction is ignored — both sides are always evaluated
    - No eligible candidate yields ``None`` fields for that side

    This pure function does not persist prior objectives. Live orchestration
    uses the stateful ``ObjectiveEngine`` below.
    """
    snapshot, _report, _high, _low = _evaluate_structural_candidates(inputs)
    return snapshot


@dataclass(frozen=True, slots=True)
class _StoredObjective:
    price: float
    strength: float
    confirmed_at: float | None

    @classmethod
    def from_diagnostic(cls, candidate: SwingDiagnostic) -> _StoredObjective:
        return cls(
            price=candidate.price,
            strength=candidate.current_strength,
            confirmed_at=candidate.confirmed_at,
        )


def _same_objective(
    stored: _StoredObjective,
    candidate: SwingDiagnostic,
) -> bool:
    return (
        stored.price == candidate.price
        and stored.strength == candidate.current_strength
        and stored.confirmed_at == candidate.confirmed_at
    )


def _find_previous_diagnostic(
    stored: _StoredObjective,
    candidates: Sequence[SwingDiagnostic],
) -> SwingDiagnostic | None:
    return next(
        (candidate for candidate in candidates if _same_objective(stored, candidate)),
        None,
    )


def _reconcile_side(
    *,
    previous: _StoredObjective | None,
    current_pick: SwingDiagnostic | None,
    candidates: Sequence[SwingDiagnostic],
    side: SwingSide,
    current_price: float,
    tick_size: float,
) -> tuple[_StoredObjective | None, ObjectivePersistenceState | None]:
    """Apply independent HIGH/LOW persistence rules."""
    if previous is None:
        if current_pick is None:
            return None, None
        return (
            _StoredObjective.from_diagnostic(current_pick),
            ObjectivePersistenceState.NEW,
        )

    previous_diagnostic = _find_previous_diagnostic(previous, candidates)
    confirmed_broken = (
        previous_diagnostic is not None
        and previous_diagnostic.lifecycle is LifecycleState.CONFIRMED_BROKEN
    )
    if confirmed_broken:
        # Preserve the public ObjectiveSnapshot API: BREACHED now means the
        # underlying structural lifecycle reached CONFIRMED_BROKEN.
        return None, ObjectivePersistenceState.BREACHED

    if (
        previous_diagnostic is not None
        and previous_diagnostic.lifecycle is LifecycleState.SUPERSEDED
    ):
        replacement = (
            _StoredObjective.from_diagnostic(current_pick)
            if current_pick is not None
            else None
        )
        return replacement, ObjectivePersistenceState.SUPERSEDED

    previous_distance = abs(previous.price - current_price) / tick_size
    if (
        current_pick is not None
        and not _same_objective(previous, current_pick)
        and current_pick.distance_ticks < previous_distance
    ):
        return (
            _StoredObjective.from_diagnostic(current_pick),
            ObjectivePersistenceState.REPLACED,
        )

    return previous, ObjectivePersistenceState.PERSISTED


class ObjectiveEngine:
    """Stateful Objective Engine with independent HIGH/LOW persistence."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = ObjectiveSnapshot.empty(timestamp=self._clock())
        self._active_high: _StoredObjective | None = None
        self._active_low: _StoredObjective | None = None
        self._invalidated_highs: set[_StoredObjective] = set()
        self._invalidated_lows: set[_StoredObjective] = set()
        self._structural_hierarchy = PersistentStructuralHierarchy()

    def evaluate(self, inputs: ObjectiveInputs) -> ObjectiveSnapshot:
        """Evaluate, reconcile, and retain persistent objectives."""
        if active_structural_hierarchy() is None:
            with use_structural_hierarchy(self._structural_hierarchy):
                _current, report, _high_pick, _low_pick = (
                    _evaluate_structural_candidates(inputs)
                )
        else:
            _current, report, _high_pick, _low_pick = (
                _evaluate_structural_candidates(inputs)
            )
        if report is None:
            # Invalid/empty classification must not erase an existing objective.
            self._latest = ObjectiveSnapshot(
                nearest_high_price=self._latest.nearest_high_price,
                nearest_high_distance_ticks=self._latest.nearest_high_distance_ticks,
                nearest_high_strength=self._latest.nearest_high_strength,
                nearest_low_price=self._latest.nearest_low_price,
                nearest_low_distance_ticks=self._latest.nearest_low_distance_ticks,
                nearest_low_strength=self._latest.nearest_low_strength,
                current_price=(
                    inputs.current_price
                    if _is_finite(inputs.current_price)
                    else self._latest.current_price
                ),
                timestamp=inputs.timestamp,
                high_state=(
                    ObjectivePersistenceState.PERSISTED
                    if self._active_high is not None
                    else None
                ),
                low_state=(
                    ObjectivePersistenceState.PERSISTED
                    if self._active_low is not None
                    else None
                ),
            )
            return self._latest

        high_pick = _pick_nearest_eligible(
            tuple(
                candidate
                for candidate in report.highs
                if _StoredObjective.from_diagnostic(candidate)
                not in self._invalidated_highs
            ),
            side=SwingSide.HIGH,
            current_price=inputs.current_price,
        )
        low_pick = _pick_nearest_eligible(
            tuple(
                candidate
                for candidate in report.lows
                if _StoredObjective.from_diagnostic(candidate)
                not in self._invalidated_lows
            ),
            side=SwingSide.LOW,
            current_price=inputs.current_price,
        )

        previous_high = self._active_high
        self._active_high, high_state = _reconcile_side(
            previous=self._active_high,
            current_pick=high_pick,
            candidates=report.highs,
            side=SwingSide.HIGH,
            current_price=inputs.current_price,
            tick_size=inputs.tick_size,
        )
        if (
            previous_high is not None
            and high_state
            in {
                ObjectivePersistenceState.BREACHED,
                ObjectivePersistenceState.SUPERSEDED,
            }
        ):
            self._invalidated_highs.add(previous_high)

        previous_low = self._active_low
        self._active_low, low_state = _reconcile_side(
            previous=self._active_low,
            current_pick=low_pick,
            candidates=report.lows,
            side=SwingSide.LOW,
            current_price=inputs.current_price,
            tick_size=inputs.tick_size,
        )
        if (
            previous_low is not None
            and low_state
            in {
                ObjectivePersistenceState.BREACHED,
                ObjectivePersistenceState.SUPERSEDED,
            }
        ):
            self._invalidated_lows.add(previous_low)

        high = self._active_high
        low = self._active_low
        self._latest = ObjectiveSnapshot(
            nearest_high_price=high.price if high else None,
            nearest_high_distance_ticks=(
                abs(high.price - inputs.current_price) / inputs.tick_size
                if high
                else None
            ),
            nearest_high_strength=high.strength if high else None,
            nearest_low_price=low.price if low else None,
            nearest_low_distance_ticks=(
                abs(low.price - inputs.current_price) / inputs.tick_size
                if low
                else None
            ),
            nearest_low_strength=low.strength if low else None,
            current_price=inputs.current_price,
            timestamp=inputs.timestamp,
            high_state=high_state,
            low_state=low_state,
        )
        return self._latest

    def snapshot(self) -> ObjectiveSnapshot:
        """Return the latest snapshot without re-evaluating."""
        return self._latest
