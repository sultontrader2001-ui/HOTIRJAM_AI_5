"""Tests for Initiative Engine detectors and H-6 observation path."""

from __future__ import annotations

import math

from hotirjam_ai5.initiative import (
    InitiativeEngine,
    InitiativeInputs,
    InitiativeSide,
    InitiativeState,
    OhlcCandle,
    analyze_candle_strength,
    detect_impulse,
    detect_momentum,
    evaluate_initiative,
)
from hotirjam_ai5.objective import ObjectiveSnapshot


TICK = 0.25


def _c(o: float, h: float, l: float, c: float, *, volume: float = 100.0) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=volume)


def _up_candles() -> tuple[OhlcCandle, ...]:
    return (
        _c(100.0, 100.5, 99.8, 100.4),
        _c(100.4, 101.0, 100.2, 100.9),
        _c(100.9, 101.5, 100.7, 101.4),
        _c(101.4, 102.0, 101.2, 101.9),
        _c(101.9, 102.5, 101.7, 102.4),
        _c(102.4, 103.0, 102.2, 102.9),
    )


def _down_candles() -> tuple[OhlcCandle, ...]:
    return (
        _c(103.0, 103.2, 102.5, 102.6),
        _c(102.6, 102.7, 102.0, 102.1),
        _c(102.1, 102.2, 101.5, 101.6),
        _c(101.6, 101.7, 101.0, 101.1),
        _c(101.1, 101.2, 100.5, 100.6),
        _c(100.6, 100.7, 100.0, 100.1),
    )


def _flat_candles() -> tuple[OhlcCandle, ...]:
    return tuple(_c(100.0, 100.1, 99.9, 100.0) for _ in range(6))


def _objectives(*, complete: bool = True) -> ObjectiveSnapshot | None:
    if not complete:
        return ObjectiveSnapshot.empty(timestamp=1.0, current_price=100.0)
    return ObjectiveSnapshot(
        nearest_high_price=105.0,
        nearest_high_distance_ticks=20.0,
        nearest_high_strength=60.0,
        nearest_low_price=95.0,
        nearest_low_distance_ticks=20.0,
        nearest_low_strength=60.0,
        current_price=100.0,
        timestamp=1.0,
    )


def _inputs(
    candles: tuple[OhlcCandle, ...],
    *,
    objectives: ObjectiveSnapshot | None = None,
    tick_size: float = TICK,
    timestamp: float = 1_700_000_000.0,
) -> InitiativeInputs:
    return InitiativeInputs(
        candles=candles,
        tick_size=tick_size,
        timestamp=timestamp,
        objectives=objectives if objectives is not None else _objectives(),
    )


def test_impulse_buyer_and_seller() -> None:
    buy = detect_impulse(_up_candles(), tick_size=TICK)
    sell = detect_impulse(_down_candles(), tick_size=TICK)
    none = detect_impulse(_flat_candles(), tick_size=TICK)
    assert buy.side is InitiativeSide.BUYER or buy.side.value == "BUYER"
    assert sell.side is InitiativeSide.SELLER or sell.side.value == "SELLER"
    assert none.side.value == "NONE"


def test_momentum_and_candle_strength_smoke() -> None:
    mom = detect_momentum(_up_candles(), tick_size=TICK)
    cndl = analyze_candle_strength(_up_candles())
    assert mom.score >= 0.0
    assert cndl.score >= 0.0


def test_evaluate_buyer_seller_none() -> None:
    buyer = evaluate_initiative(_inputs(_up_candles()))
    seller = evaluate_initiative(_inputs(_down_candles()))
    flat = evaluate_initiative(_inputs(_flat_candles()))
    assert buyer.dominant_side is InitiativeSide.BUYER
    assert seller.dominant_side is InitiativeSide.SELLER
    assert flat.dominant_side is InitiativeSide.NONE
    assert buyer.initiative_state in {
        InitiativeState.EMERGING,
        InitiativeState.DOMINANT,
    }
    assert 0.0 <= buyer.confidence <= 100.0
    assert buyer.evidence.force >= 0.0
    assert buyer.reasons


def test_empty_and_invalid_inputs() -> None:
    empty = evaluate_initiative(_inputs(()))
    assert empty.dominant_side is InitiativeSide.NONE
    invalid = evaluate_initiative(_inputs(_up_candles(), tick_size=0.0))
    assert invalid.dominant_side is InitiativeSide.NONE


def test_nan_candles_ignored() -> None:
    bad = (
        _c(math.nan, 101.0, 99.0, 100.0),
        *_up_candles(),
    )
    snap = evaluate_initiative(_inputs(bad))
    assert snap.dominant_side in {InitiativeSide.BUYER, InitiativeSide.NONE}


def test_engine_retains_latest_and_is_deterministic() -> None:
    engine = InitiativeEngine(clock=lambda: 1.0)
    first = engine.evaluate(_inputs(_up_candles(), timestamp=10.0))
    assert engine.snapshot() is first
    inputs = _inputs(_up_candles(), timestamp=11.0)
    assert evaluate_initiative(inputs) == evaluate_initiative(inputs)


def test_scores_clamped() -> None:
    snap = evaluate_initiative(_inputs(_up_candles()))
    assert 0.0 <= snap.buyer_initiative <= 100.0
    assert 0.0 <= snap.seller_initiative <= 100.0
    assert 0.0 <= snap.confidence <= 100.0
