"""Anomaly detectors for Objective Engineering Validation Phase A."""

from __future__ import annotations

from enum import StrEnum

from hotirjam_ai5.objective.objective_snapshot import ObjectivePersistenceState
from hotirjam_ai5.objective_engineering.models import ObjectiveSide, ReasonClass
from hotirjam_ai5.objective_engineering.reasons import identity_changed


class AnomalyCode(StrEnum):
    UNEXPECTED_REPLACEMENT = "UNEXPECTED_REPLACEMENT"
    SIDE_COUPLING = "SIDE_COUPLING"
    UNEXPLAINED_FLICKER = "UNEXPLAINED_FLICKER"
    INVALID_NONE = "INVALID_NONE"
    IMPOSSIBLE_TRANSITION = "IMPOSSIBLE_TRANSITION"


_TERMINAL = frozenset(
    {
        ObjectivePersistenceState.BREACHED,
        ObjectivePersistenceState.SUPERSEDED,
    }
)

_ACTIVE_STATES = frozenset(
    {
        ObjectivePersistenceState.NEW,
        ObjectivePersistenceState.PERSISTED,
        ObjectivePersistenceState.REPLACED,
        ObjectivePersistenceState.SUPERSEDED,
    }
)


def check_invalid_none(
    *,
    price: float | None,
    state: ObjectivePersistenceState | None,
) -> str | None:
    if price is None and state in _ACTIVE_STATES:
        if state is ObjectivePersistenceState.SUPERSEDED:
            # SUPERSEDED may clear to None — allowed.
            return None
        return f"price=None with active state={state.value}"
    if price is not None and state is ObjectivePersistenceState.BREACHED:
        return f"BREACHED retaining price={price}"
    return None


def check_impossible_transition(
    *,
    previous_price: float | None,
    previous_state: ObjectivePersistenceState | None,
    current_price: float | None,
    current_state: ObjectivePersistenceState | None,
) -> str | None:
    if previous_price is None and previous_state is None:
        if current_state in {
            ObjectivePersistenceState.REPLACED,
            ObjectivePersistenceState.BREACHED,
            ObjectivePersistenceState.SUPERSEDED,
            ObjectivePersistenceState.PERSISTED,
        }:
            return (
                f"empty→{current_state.value} without NEW "
                f"(price={current_price})"
            )
    if (
        current_state is ObjectivePersistenceState.REPLACED
        and previous_price is not None
        and current_price == previous_price
    ):
        return "REPLACED with identical price identity"
    if (
        current_state is ObjectivePersistenceState.NEW
        and current_price is None
    ):
        return "NEW without price"
    if (
        current_state is ObjectivePersistenceState.PERSISTED
        and current_price is None
    ):
        return "PERSISTED without price"
    return None


def check_unexpected_replacement(
    *,
    current_state: ObjectivePersistenceState | None,
    reason: ReasonClass,
) -> str | None:
    if (
        current_state is ObjectivePersistenceState.REPLACED
        and reason is ReasonClass.UNEXPECTED_NOT_NEARER
    ):
        return "REPLACED but new distance is not nearer than previous"
    return None


def check_side_coupling(
    *,
    high_prev_price: float | None,
    high_price: float | None,
    high_prev_state: ObjectivePersistenceState | None,
    high_state: ObjectivePersistenceState | None,
    low_prev_price: float | None,
    low_price: float | None,
    low_prev_state: ObjectivePersistenceState | None,
    low_state: ObjectivePersistenceState | None,
) -> str | None:
    """Both sides identity-change while both were PERSISTED and neither terminal."""
    high_id = identity_changed(high_prev_price, high_price)
    low_id = identity_changed(low_prev_price, low_price)
    if not (high_id and low_id):
        return None
    if high_prev_state is not ObjectivePersistenceState.PERSISTED:
        return None
    if low_prev_state is not ObjectivePersistenceState.PERSISTED:
        return None
    if high_state in _TERMINAL or low_state in _TERMINAL:
        return None
    return (
        "both HIGH and LOW identity changed on one evaluate "
        f"(H {high_prev_price}→{high_price} {high_state}; "
        f"L {low_prev_price}→{low_price} {low_state})"
    )


def check_flicker(
    *,
    history: list[float | None],
    current_price: float | None,
    current_state: ObjectivePersistenceState | None,
    window: int = 3,
) -> str | None:
    """A→B→A within ``window`` identity steps without terminal justification."""
    if current_state in _TERMINAL:
        return None
    if len(history) < 2:
        return None
    # history is prior identities oldest→newest (excluding current).
    recent = history[-(window):]
    if len(recent) < 2:
        return None
    # Look for pattern ... A, B, A where current is A and last two prior end with B, and A before B.
    if recent[-1] == current_price:
        return None
    if len(recent) >= 2 and recent[-2] == current_price and recent[-1] != current_price:
        # Prior: ... A, B  and current A → flicker
        if recent[-1] is not None and current_price is not None:
            return (
                f"flicker identity {current_price}→{recent[-1]}→{current_price} "
                f"within {window} evaluates"
            )
    # Broader: current equals some identity within window that is not the immediate previous.
    if current_price is None:
        return None
    if recent[-1] == current_price:
        return None
    for older in recent[:-1]:
        if older == current_price and recent[-1] != current_price:
            return (
                f"flicker reversion to {current_price} after {recent[-1]} "
                f"within {window} evaluates"
            )
    return None


def side_label(high: bool) -> ObjectiveSide:
    return ObjectiveSide.HIGH if high else ObjectiveSide.LOW
