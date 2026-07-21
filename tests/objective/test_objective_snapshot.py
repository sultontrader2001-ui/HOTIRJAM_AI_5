"""Tests for ObjectiveSnapshot (Module 01)."""

from __future__ import annotations

from hotirjam_ai5.objective import ObjectivePersistenceState, ObjectiveSnapshot


def test_empty_snapshot_has_no_objectives() -> None:
    snap = ObjectiveSnapshot.empty(timestamp=1_700_000_000.0, current_price=100.0)
    assert snap.nearest_high_price is None
    assert snap.nearest_low_price is None
    assert snap.nearest_high_distance_ticks is None
    assert snap.nearest_low_distance_ticks is None
    assert snap.nearest_high_strength is None
    assert snap.nearest_low_strength is None
    assert snap.current_price == 100.0
    assert snap.timestamp == 1_700_000_000.0
    assert snap.high_state is None
    assert snap.low_state is None
    assert not snap.has_high
    assert not snap.has_low
    assert not snap.is_complete


def test_complete_snapshot_flags() -> None:
    snap = ObjectiveSnapshot(
        nearest_high_price=105.0,
        nearest_high_distance_ticks=20.0,
        nearest_high_strength=70.0,
        nearest_low_price=98.0,
        nearest_low_distance_ticks=8.0,
        nearest_low_strength=55.0,
        current_price=100.0,
        timestamp=1.0,
        high_state=ObjectivePersistenceState.NEW,
        low_state=ObjectivePersistenceState.PERSISTED,
    )
    assert snap.has_high
    assert snap.has_low
    assert snap.is_complete
    assert snap.high_state is ObjectivePersistenceState.NEW
    assert snap.low_state is ObjectivePersistenceState.PERSISTED


def test_partial_high_only_not_complete() -> None:
    snap = ObjectiveSnapshot(
        nearest_high_price=105.0,
        nearest_high_distance_ticks=20.0,
        nearest_high_strength=70.0,
        nearest_low_price=None,
        nearest_low_distance_ticks=None,
        nearest_low_strength=None,
        current_price=100.0,
        timestamp=1.0,
    )
    assert snap.has_high
    assert not snap.has_low
    assert not snap.is_complete


def test_snapshot_is_frozen() -> None:
    snap = ObjectiveSnapshot.empty(timestamp=0.0)
    try:
        snap.current_price = 1.0  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("ObjectiveSnapshot must be immutable")
