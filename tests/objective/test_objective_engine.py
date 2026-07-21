"""Tests for Objective Engine (Module 01).

Pure battlefield description — no Decision / trade wiring.
"""

from __future__ import annotations

import math

from hotirjam_ai5.objective import (
    ConfirmedSwing,
    ObjectiveEngine,
    ObjectiveInputs,
    ObjectivePersistenceState,
    ObjectiveSnapshot,
    evaluate_objectives,
)


TICK = 0.25


def _swing(price: float, strength: float = 50.0, *, at: float | None = None) -> ConfirmedSwing:
    return ConfirmedSwing(price=price, strength=strength, confirmed_at=at)


def _inputs(
    *,
    price: float = 100.0,
    tick_size: float = TICK,
    highs: tuple[ConfirmedSwing, ...] = (),
    lows: tuple[ConfirmedSwing, ...] = (),
    timestamp: float = 1_700_000_000.0,
) -> ObjectiveInputs:
    return ObjectiveInputs(
        current_price=price,
        tick_size=tick_size,
        confirmed_highs=highs,
        confirmed_lows=lows,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------- selection


def test_nearest_eligible_major_high_selection() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(
                _swing(106.0, 60.0, at=1.0),
                _swing(108.0, 90.0, at=2.0),
            ),
            lows=(_swing(94.0, 50.0, at=1.5),),
        )
    )
    assert snap.nearest_high_price == 106.0
    assert snap.nearest_high_strength == 60.0
    assert snap.nearest_high_distance_ticks == (106.0 - 100.0) / TICK


def test_nearest_eligible_major_low_selection() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(106.0, 50.0, at=1.5),),
            lows=(
                _swing(94.0, 55.0, at=1.0),
                _swing(92.0, 80.0, at=2.0),
            ),
        )
    )
    assert snap.nearest_low_price == 94.0
    assert snap.nearest_low_strength == 55.0
    assert snap.nearest_low_distance_ticks == (100.0 - 94.0) / TICK


def test_both_sides_always_evaluated_ignores_trade_direction() -> None:
    """Rule 3: both nearest High and Low must be identified together."""
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(106.0, 70.0, at=1.0), _swing(108.0, 40.0, at=2.0)),
            lows=(_swing(94.0, 65.0, at=1.0), _swing(92.0, 40.0, at=2.0)),
        )
    )
    assert snap.is_complete
    assert snap.nearest_high_price == 106.0
    assert snap.nearest_low_price == 94.0


def test_distance_calculation() -> None:
    snap = evaluate_objectives(
        _inputs(
            price=20100.0,
            tick_size=0.25,
            highs=(_swing(20104.0, 50.0),),
            lows=(_swing(20096.0, 50.0),),
        )
    )
    assert snap.nearest_high_distance_ticks == 16.0
    assert snap.nearest_low_distance_ticks == 16.0


def test_nearest_minor_is_ignored_for_farther_eligible_major() -> None:
    """Regression: old nearest-swing behavior must never return."""
    snap = evaluate_objectives(
        _inputs(
            highs=(
                _swing(110.0, 90.0, at=1.0),  # root MAJOR
                _swing(101.0, 40.0, at=2.0),  # nested MINOR, nearer
            ),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    assert snap.nearest_high_price == 110.0
    assert snap.nearest_high_price != 101.0


def test_no_eligible_candidate_returns_none_without_fallback() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(101.0, 40.0, at=1.0),),
            lows=(_swing(99.0, 40.0, at=1.0),),
        )
    )
    assert snap.nearest_high_price is None
    assert snap.nearest_high_distance_ticks is None
    assert snap.nearest_high_strength is None
    assert snap.nearest_low_price is None
    assert snap.nearest_low_distance_ticks is None
    assert snap.nearest_low_strength is None


# ---------------------------------------------------------------- empty / invalid


def test_empty_input_returns_empty_objectives() -> None:
    snap = evaluate_objectives(_inputs())
    assert snap.current_price == 100.0
    assert snap.nearest_high_price is None
    assert snap.nearest_low_price is None
    assert not snap.is_complete


def test_invalid_swings_ignored() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(
                _swing(math.nan, 50.0),
                _swing(105.0, math.inf),
                _swing(104.0, -1.0),
                _swing(103.0, 101.0),
                _swing(106.0, 80.0),  # only valid structural high
            ),
            lows=(
                _swing(math.nan, 50.0),
                _swing(94.0, 70.0),
            ),
        )
    )
    assert snap.nearest_high_price == 106.0
    assert snap.nearest_high_strength == 80.0
    assert snap.nearest_low_price == 94.0


def test_highs_at_or_below_price_ignored() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(
                _swing(100.0, 90.0, at=1.0),
                _swing(99.0, 90.0, at=2.0),
                _swing(106.0, 50.0, at=3.0),
            ),
            lows=(_swing(94.0, 50.0, at=1.5),),
        )
    )
    assert snap.nearest_high_price == 106.0


def test_lows_at_or_above_price_ignored() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(106.0, 50.0, at=1.5),),
            lows=(
                _swing(100.0, 90.0, at=1.0),
                _swing(101.0, 90.0, at=2.0),
                _swing(94.0, 50.0, at=3.0),
            ),
        )
    )
    assert snap.nearest_low_price == 94.0


def test_invalid_tick_size() -> None:
    snap = evaluate_objectives(
        _inputs(
            tick_size=0.0,
            highs=(_swing(101.0),),
            lows=(_swing(99.0),),
        )
    )
    assert snap.nearest_high_price is None
    assert snap.nearest_low_price is None
    assert snap.current_price == 100.0


def test_non_finite_current_price() -> None:
    snap = evaluate_objectives(
        _inputs(
            price=math.nan,
            highs=(_swing(101.0),),
            lows=(_swing(99.0),),
        )
    )
    assert snap.current_price is None
    assert snap.nearest_high_price is None


# ---------------------------------------------------------------- ties / edges


def test_equal_distance_prefers_higher_strength() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(106.0, 40.0), _swing(106.0, 90.0)),
            lows=(_swing(94.0, 30.0), _swing(94.0, 75.0)),
        )
    )
    assert snap.nearest_high_strength == 90.0
    assert snap.nearest_low_strength == 75.0


def test_equal_distance_and_strength_is_order_independent() -> None:
    """Identical pivots: selection is deterministic regardless of input order."""
    early = _swing(106.0, 50.0)
    late = _swing(106.0, 50.0)
    a = evaluate_objectives(_inputs(highs=(early, late), lows=(_swing(94.0),)))
    b = evaluate_objectives(_inputs(highs=(late, early), lows=(_swing(94.0),)))
    assert a == b
    assert a.nearest_high_price == 106.0
    assert a.nearest_high_strength == 50.0


def test_only_high_side_has_no_eligible_structural_objective() -> None:
    snap = evaluate_objectives(_inputs(highs=(_swing(103.0, 60.0),), lows=()))
    assert not snap.has_high
    assert not snap.has_low
    assert not snap.is_complete


def test_only_low_side_has_no_eligible_structural_objective() -> None:
    snap = evaluate_objectives(_inputs(highs=(), lows=(_swing(97.0, 60.0),)))
    assert not snap.has_high
    assert not snap.has_low


def test_engine_retains_latest_snapshot() -> None:
    clock = iter([1.0, 2.0, 3.0]).__next__
    engine = ObjectiveEngine(clock=clock)
    assert isinstance(engine.snapshot(), ObjectiveSnapshot)
    assert not engine.snapshot().is_complete

    first = engine.evaluate(
        _inputs(
            timestamp=10.0,
            highs=(_swing(106.0, 40.0),),
            lows=(_swing(94.0, 40.0),),
        )
    )
    assert engine.snapshot() is first
    assert first.is_complete
    assert first.high_state is ObjectivePersistenceState.NEW
    assert first.low_state is ObjectivePersistenceState.NEW

    second = engine.evaluate(_inputs(timestamp=11.0))
    assert engine.snapshot() is second
    assert second.is_complete
    assert second.nearest_high_price == 106.0
    assert second.nearest_low_price == 94.0
    assert second.high_state is ObjectivePersistenceState.PERSISTED
    assert second.low_state is ObjectivePersistenceState.PERSISTED


def test_persistent_low_survives_evaluation_with_no_candidate() -> None:
    engine = ObjectiveEngine(clock=lambda: 0.0)
    first = engine.evaluate(
        _inputs(
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    assert first.nearest_low_price == 90.0
    assert first.low_state is ObjectivePersistenceState.NEW

    second = engine.evaluate(_inputs(timestamp=2.0))
    assert second.nearest_low_price == 90.0
    assert second.low_state is ObjectivePersistenceState.PERSISTED


def test_nearer_nested_low_does_not_replace_persistent_major() -> None:
    engine = ObjectiveEngine(clock=lambda: 0.0)
    first = engine.evaluate(
        _inputs(
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    assert first.nearest_low_price == 90.0

    # The old LOW remains in persistent hierarchy even when absent from rolling
    # input. The nearer higher LOW stays nested and cannot become a root MAJOR.
    second = engine.evaluate(
        _inputs(
            timestamp=2.0,
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(94.0, 80.0, at=2.0),),
        )
    )
    assert second.nearest_low_price == 90.0
    assert second.low_state is ObjectivePersistenceState.PERSISTED


def test_penetrated_low_survives_as_challenged() -> None:
    engine = ObjectiveEngine(clock=lambda: 0.0)
    engine.evaluate(
        _inputs(
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    challenged = engine.evaluate(
        _inputs(
            price=89.0,
            timestamp=2.0,
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    assert challenged.nearest_low_price == 90.0
    assert challenged.low_state is ObjectivePersistenceState.PERSISTED

    # A price return alone does not resolve lifecycle, but cannot erase it.
    reclaimed = engine.evaluate(
        _inputs(
            price=100.0,
            timestamp=3.0,
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    assert reclaimed.nearest_low_price == 90.0
    assert reclaimed.low_state is ObjectivePersistenceState.PERSISTED


def test_invalid_evaluation_does_not_clear_active_objectives() -> None:
    engine = ObjectiveEngine(clock=lambda: 0.0)
    engine.evaluate(
        _inputs(
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    invalid = engine.evaluate(_inputs(tick_size=0.0, timestamp=2.0))
    assert invalid.nearest_high_price == 110.0
    assert invalid.nearest_low_price == 90.0
    assert invalid.high_state is ObjectivePersistenceState.PERSISTED
    assert invalid.low_state is ObjectivePersistenceState.PERSISTED


def test_high_and_low_persistence_are_independent() -> None:
    engine = ObjectiveEngine(clock=lambda: 0.0)
    engine.evaluate(
        _inputs(
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    updated = engine.evaluate(_inputs(price=111.0, timestamp=2.0))
    assert updated.nearest_high_price == 110.0
    assert updated.high_state is ObjectivePersistenceState.PERSISTED
    assert updated.nearest_low_price == 90.0
    assert updated.low_state is ObjectivePersistenceState.PERSISTED


def test_superseded_low_is_replaced_and_reported() -> None:
    engine = ObjectiveEngine(clock=lambda: 0.0)
    engine.evaluate(
        _inputs(
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(_swing(90.0, 80.0, at=1.5),),
        )
    )
    updated = engine.evaluate(
        _inputs(
            timestamp=2.0,
            highs=(_swing(110.0, 90.0, at=1.0),),
            lows=(
                _swing(90.0, 80.0, at=1.5),
                _swing(89.75, 85.0, at=2.0),
            ),
        )
    )
    assert updated.nearest_low_price == 89.75
    assert updated.low_state is ObjectivePersistenceState.SUPERSEDED


def test_evaluate_is_deterministic() -> None:
    inputs = _inputs(
        highs=(_swing(106.0, 55.0, at=1.0), _swing(108.0, 40.0, at=2.0)),
        lows=(_swing(94.0, 55.0, at=1.0), _swing(92.0, 40.0, at=2.0)),
    )
    a = evaluate_objectives(inputs)
    b = evaluate_objectives(inputs)
    assert a == b
