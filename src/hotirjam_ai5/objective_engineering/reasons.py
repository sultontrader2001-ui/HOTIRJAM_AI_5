"""Infer replace / breach reason classes from consecutive snapshots.

Read-only. Does not call or modify ObjectiveEngine.
"""

from __future__ import annotations

from hotirjam_ai5.objective.objective_snapshot import (
    ObjectivePersistenceState,
    ObjectiveSnapshot,
)
from hotirjam_ai5.objective_engineering.models import ReasonClass


def _state_str(state: ObjectivePersistenceState | None) -> str | None:
    return None if state is None else str(state.value)


def infer_side_reason(
    *,
    previous_price: float | None,
    previous_distance: float | None,
    previous_state: ObjectivePersistenceState | None,
    current_price: float | None,
    current_distance: float | None,
    current_state: ObjectivePersistenceState | None,
) -> ReasonClass:
    """Map one side's before/after fields to a reason class."""
    if current_state is None and current_price is None:
        if previous_price is None:
            return ReasonClass.NONE
        # Cleared without an explicit breach/supersede state on this sample.
        if previous_state in {
            ObjectivePersistenceState.BREACHED,
            ObjectivePersistenceState.SUPERSEDED,
        }:
            # Prior sample already carried terminal state; now empty.
            if previous_state is ObjectivePersistenceState.BREACHED:
                return ReasonClass.CONFIRMED_BROKEN
            return ReasonClass.LIFECYCLE_SUPERSEDED
        return ReasonClass.CLEARED_UNEXPLAINED

    if current_state is ObjectivePersistenceState.NEW:
        return ReasonClass.FIRST_ASSIGNMENT
    if current_state is ObjectivePersistenceState.PERSISTED:
        return ReasonClass.UNCHANGED
    if current_state is ObjectivePersistenceState.BREACHED:
        return ReasonClass.CONFIRMED_BROKEN
    if current_state is ObjectivePersistenceState.SUPERSEDED:
        return ReasonClass.LIFECYCLE_SUPERSEDED
    if current_state is ObjectivePersistenceState.REPLACED:
        if (
            previous_distance is not None
            and current_distance is not None
            and current_distance < previous_distance
        ):
            return ReasonClass.NEARER_ELIGIBLE
        if previous_price is not None and current_price == previous_price:
            return ReasonClass.UNEXPECTED_NOT_NEARER
        if (
            previous_distance is not None
            and current_distance is not None
            and current_distance >= previous_distance
        ):
            return ReasonClass.UNEXPECTED_NOT_NEARER
        # Missing prior distance — treat as nearer-eligible by contract default.
        return ReasonClass.NEARER_ELIGIBLE

    # State missing but price present.
    if current_price is not None:
        if previous_price is None:
            return ReasonClass.FIRST_ASSIGNMENT
        if current_price == previous_price:
            return ReasonClass.UNCHANGED
        return ReasonClass.NEARER_ELIGIBLE
    return ReasonClass.NONE


def side_fields(snapshot: ObjectiveSnapshot, *, high: bool) -> tuple[
    float | None,
    float | None,
    float | None,
    ObjectivePersistenceState | None,
]:
    if high:
        return (
            snapshot.nearest_high_price,
            snapshot.nearest_high_distance_ticks,
            snapshot.nearest_high_strength,
            snapshot.high_state,
        )
    return (
        snapshot.nearest_low_price,
        snapshot.nearest_low_distance_ticks,
        snapshot.nearest_low_strength,
        snapshot.low_state,
    )


def identity_changed(
    previous_price: float | None,
    current_price: float | None,
) -> bool:
    return previous_price != current_price


def state_changed(
    previous_state: ObjectivePersistenceState | None,
    current_state: ObjectivePersistenceState | None,
) -> bool:
    return _state_str(previous_state) != _state_str(current_state)
