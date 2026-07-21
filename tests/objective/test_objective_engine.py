"""Tests for Objective Engine (Module 01).

Pure battlefield description — no Decision / trade wiring.
"""

from __future__ import annotations

import math

from hotirjam_ai5.objective import (
    ConfirmedSwing,
    ObjectiveEngine,
    ObjectiveInputs,
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


def test_nearest_high_selection() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(
                _swing(110.0, 40.0),
                _swing(102.0, 60.0),  # nearest above
                _swing(105.0, 90.0),
            ),
            lows=(_swing(95.0, 50.0),),
        )
    )
    assert snap.nearest_high_price == 102.0
    assert snap.nearest_high_strength == 60.0
    assert snap.nearest_high_distance_ticks == (102.0 - 100.0) / TICK


def test_nearest_low_selection() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(105.0, 50.0),),
            lows=(
                _swing(90.0, 40.0),
                _swing(98.0, 55.0),  # nearest below
                _swing(94.0, 80.0),
            ),
        )
    )
    assert snap.nearest_low_price == 98.0
    assert snap.nearest_low_strength == 55.0
    assert snap.nearest_low_distance_ticks == (100.0 - 98.0) / TICK


def test_both_sides_always_evaluated_ignores_trade_direction() -> None:
    """Rule 3: both nearest High and Low must be identified together."""
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(101.0, 70.0), _swing(108.0, 40.0)),
            lows=(_swing(99.0, 65.0), _swing(92.0, 40.0)),
        )
    )
    assert snap.is_complete
    assert snap.nearest_high_price == 101.0
    assert snap.nearest_low_price == 99.0


def test_distance_calculation() -> None:
    snap = evaluate_objectives(
        _inputs(
            price=20100.0,
            tick_size=0.25,
            highs=(_swing(20101.0, 50.0),),
            lows=(_swing(20099.0, 50.0),),
        )
    )
    assert snap.nearest_high_distance_ticks == 4.0
    assert snap.nearest_low_distance_ticks == 4.0


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
                _swing(102.0, 80.0),  # only valid high above price
            ),
            lows=(
                _swing(math.nan, 50.0),
                _swing(98.0, 70.0),
            ),
        )
    )
    assert snap.nearest_high_price == 102.0
    assert snap.nearest_high_strength == 80.0
    assert snap.nearest_low_price == 98.0


def test_highs_at_or_below_price_ignored() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(100.0, 90.0), _swing(99.0, 90.0), _swing(101.0, 50.0)),
            lows=(_swing(99.0, 50.0),),
        )
    )
    assert snap.nearest_high_price == 101.0


def test_lows_at_or_above_price_ignored() -> None:
    snap = evaluate_objectives(
        _inputs(
            highs=(_swing(101.0, 50.0),),
            lows=(_swing(100.0, 90.0), _swing(101.0, 90.0), _swing(99.0, 50.0)),
        )
    )
    assert snap.nearest_low_price == 99.0


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
            highs=(_swing(102.0, 40.0), _swing(102.0, 90.0)),
            lows=(_swing(98.0, 30.0), _swing(98.0, 75.0)),
        )
    )
    assert snap.nearest_high_strength == 90.0
    assert snap.nearest_low_strength == 75.0


def test_equal_distance_and_strength_is_order_independent() -> None:
    """Identical pivots: selection is deterministic regardless of input order."""
    early = _swing(102.0, 50.0, at=10.0)
    late = _swing(102.0, 50.0, at=20.0)
    a = evaluate_objectives(_inputs(highs=(early, late), lows=(_swing(98.0),)))
    b = evaluate_objectives(_inputs(highs=(late, early), lows=(_swing(98.0),)))
    assert a == b
    assert a.nearest_high_price == 102.0
    assert a.nearest_high_strength == 50.0


def test_only_high_side_available() -> None:
    snap = evaluate_objectives(_inputs(highs=(_swing(103.0, 60.0),), lows=()))
    assert snap.has_high
    assert not snap.has_low
    assert not snap.is_complete


def test_only_low_side_available() -> None:
    snap = evaluate_objectives(_inputs(highs=(), lows=(_swing(97.0, 60.0),)))
    assert not snap.has_high
    assert snap.has_low


def test_engine_retains_latest_snapshot() -> None:
    clock = iter([1.0, 2.0, 3.0]).__next__
    engine = ObjectiveEngine(clock=clock)
    assert isinstance(engine.snapshot(), ObjectiveSnapshot)
    assert not engine.snapshot().is_complete

    first = engine.evaluate(
        _inputs(
            timestamp=10.0,
            highs=(_swing(101.0, 40.0),),
            lows=(_swing(99.0, 40.0),),
        )
    )
    assert engine.snapshot() is first
    assert first.is_complete

    second = engine.evaluate(_inputs(timestamp=11.0))
    assert engine.snapshot() is second
    assert not second.is_complete


def test_evaluate_is_deterministic() -> None:
    inputs = _inputs(
        highs=(_swing(104.0, 55.0), _swing(101.5, 40.0)),
        lows=(_swing(96.0, 55.0), _swing(99.5, 40.0)),
    )
    a = evaluate_objectives(inputs)
    b = evaluate_objectives(inputs)
    assert a == b
