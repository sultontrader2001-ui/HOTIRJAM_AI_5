"""Tests for Continuation Engine (Module 04)."""

from __future__ import annotations

import math

from hotirjam_ai5.continuation import (
    ContinuationEngine,
    ContinuationInputs,
    ContinuationSide,
    ContinuationState,
    evaluate_continuation,
    measure_momentum_decay,
    measure_pressure_persistence,
)
from hotirjam_ai5.initiative import (
    InitiativeSide,
    InitiativeSnapshot,
    InitiativeState,
    OhlcCandle,
)
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSide, ResponseSnapshot, ResponseState


TICK = 0.25


def _c(o: float, h: float, l: float, c: float, *, volume: float = 100.0) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=volume)


def _initiative(
    side: InitiativeSide = InitiativeSide.BUYER,
    *,
    score: float = 75.0,
) -> InitiativeSnapshot:
    return InitiativeSnapshot(
        initiative_side=side,
        impulse_score=score,
        momentum_score=score,
        candle_strength_score=score,
        initiative_score=score,
        state=InitiativeState.STRONG if score >= 70 else InitiativeState.MEDIUM,
        confidence=80.0,
        reasons=("test",),
        timestamp=1.0,
    )


def _response(
    *,
    preserved: bool = True,
    state: ResponseState = ResponseState.FAILED,
    strength: float = 10.0,
) -> ResponseSnapshot:
    return ResponseSnapshot(
        response_side=ResponseSide.NONE if state is ResponseState.FAILED else ResponseSide.SELLER,
        response_strength=strength,
        response_state=state,
        initiative_preserved=preserved,
        confidence=50.0,
        reasons=("test response",),
        timestamp=1.0,
    )


def _objectives(*, price: float = 100.0) -> ObjectiveSnapshot:
    return ObjectiveSnapshot(
        nearest_high_price=price + 5.0,
        nearest_high_distance_ticks=20.0,
        nearest_high_strength=60.0,
        nearest_low_price=price - 5.0,
        nearest_low_distance_ticks=20.0,
        nearest_low_strength=60.0,
        current_price=price,
        timestamp=1.0,
    )


def _bullish_continuation(start: float = 100.0, steps: int = 6, step: float = 1.0) -> tuple[OhlcCandle, ...]:
    candles: list[OhlcCandle] = []
    price = start
    for _ in range(steps):
        nxt = price + step
        candles.append(_c(price, nxt + 0.2, price - 0.1, nxt))
        price = nxt
    return tuple(candles)


def _fading_bullish() -> tuple[OhlcCandle, ...]:
    """Strong early up move, then stall / reverse."""
    return (
        _c(100.0, 101.5, 99.9, 101.4),
        _c(101.4, 103.0, 101.2, 102.9),
        _c(102.9, 104.5, 102.8, 104.4),
        _c(104.4, 104.6, 103.5, 103.7),
        _c(103.7, 103.9, 102.5, 102.8),
        _c(102.8, 103.0, 101.5, 101.8),
    )


def _flat(price: float = 100.0, n: int = 6) -> tuple[OhlcCandle, ...]:
    return tuple(_c(price, price + 0.05, price - 0.05, price) for _ in range(n))


def _inputs(
    candles: tuple[OhlcCandle, ...],
    *,
    initiative: InitiativeSnapshot | None = None,
    response: ResponseSnapshot | None = None,
    tick_size: float = TICK,
) -> ContinuationInputs:
    return ContinuationInputs(
        objectives=_objectives(),
        initiative=initiative or _initiative(),
        response=response or _response(),
        candles=candles,
        tick_size=tick_size,
        timestamp=1_700_000_000.0,
    )


# ---------------------------------------------------------------- CT01 / CT02


def test_pressure_persistence_high_on_aligned_move() -> None:
    result = measure_pressure_persistence(
        _bullish_continuation(step=1.5),
        initiative=_initiative(InitiativeSide.BUYER, score=80.0),
        response=_response(preserved=True, state=ResponseState.FAILED),
        tick_size=TICK,
    )
    assert result.pressure_score > 40.0


def test_pressure_discounted_when_initiative_not_preserved() -> None:
    candles = _bullish_continuation(step=1.0)
    held = measure_pressure_persistence(
        candles,
        initiative=_initiative(score=70.0),
        response=_response(preserved=True, state=ResponseState.FAILED),
        tick_size=TICK,
    )
    lost = measure_pressure_persistence(
        candles,
        initiative=_initiative(score=70.0),
        response=_response(preserved=False, state=ResponseState.STRONG, strength=80.0),
        tick_size=TICK,
    )
    assert lost.pressure_score < held.pressure_score


def test_momentum_decay_low_when_accelerating() -> None:
    result = measure_momentum_decay(
        _bullish_continuation(step=1.5),
        initiative=_initiative(InitiativeSide.BUYER),
        tick_size=TICK,
    )
    assert result.momentum_decay < 50.0


def test_momentum_decay_high_when_fading() -> None:
    result = measure_momentum_decay(
        _fading_bullish(),
        initiative=_initiative(InitiativeSide.BUYER),
        tick_size=TICK,
    )
    assert result.momentum_decay > 40.0


# ---------------------------------------------------------------- Engine scenarios


def test_strong_continuation() -> None:
    snap = evaluate_continuation(
        _inputs(
            _bullish_continuation(step=1.5),
            initiative=_initiative(InitiativeSide.BUYER, score=80.0),
            response=_response(preserved=True, state=ResponseState.FAILED),
        )
    )
    assert snap.continuation_side is ContinuationSide.BUYER
    assert snap.continuation_score > 35.0
    assert snap.state in {ContinuationState.MEDIUM, ContinuationState.STRONG}
    assert snap.pressure_score > 0.0
    assert 0.0 <= snap.momentum_decay <= 100.0
    assert snap.reasons


def test_seller_continuation() -> None:
    candles: list[OhlcCandle] = []
    price = 110.0
    for _ in range(6):
        nxt = price - 1.25
        candles.append(_c(price, price + 0.1, nxt - 0.2, nxt))
        price = nxt
    snap = evaluate_continuation(
        _inputs(
            tuple(candles),
            initiative=_initiative(InitiativeSide.SELLER, score=80.0),
            response=_response(preserved=True, state=ResponseState.FAILED),
        )
    )
    assert snap.continuation_side is ContinuationSide.SELLER


def test_weak_continuation_fading() -> None:
    snap = evaluate_continuation(
        _inputs(
            _fading_bullish(),
            initiative=_initiative(InitiativeSide.BUYER, score=60.0),
            response=_response(preserved=False, state=ResponseState.STRONG, strength=75.0),
        )
    )
    assert snap.continuation_score < 70.0 or snap.state is ContinuationState.WEAK
    assert snap.momentum_decay > 30.0


def test_flat_market() -> None:
    snap = evaluate_continuation(
        _inputs(_flat(), initiative=_initiative(InitiativeSide.BUYER, score=50.0))
    )
    assert snap.continuation_side in {ContinuationSide.NONE, ContinuationSide.BUYER}
    assert snap.state in {ContinuationState.WEAK, ContinuationState.MEDIUM}


def test_no_initiative() -> None:
    snap = evaluate_continuation(
        _inputs(_bullish_continuation(), initiative=_initiative(InitiativeSide.NONE, score=0.0))
    )
    assert snap.continuation_side is ContinuationSide.NONE
    assert snap.pressure_score == 0.0


def test_empty_candles() -> None:
    snap = evaluate_continuation(_inputs(()))
    assert snap.continuation_side is ContinuationSide.NONE
    assert "Empty" in snap.reasons[0]


def test_invalid_tick_size() -> None:
    snap = evaluate_continuation(_inputs(_bullish_continuation(), tick_size=0.0))
    assert "tick" in snap.reasons[0].lower()


def test_invalid_nan_candles() -> None:
    bad = (_c(math.nan, 101, 99, 100), *_bullish_continuation())
    snap = evaluate_continuation(_inputs(bad))
    assert snap.continuation_score >= 0.0


def test_engine_retains_latest() -> None:
    engine = ContinuationEngine(clock=lambda: 3.0)
    assert engine.snapshot().continuation_side is ContinuationSide.NONE
    first = engine.evaluate(_inputs(_bullish_continuation(step=1.5)))
    assert engine.snapshot() is first
    second = engine.evaluate(_inputs(()))
    assert engine.snapshot() is second


def test_deterministic() -> None:
    inputs = _inputs(_bullish_continuation(step=1.25))
    assert evaluate_continuation(inputs) == evaluate_continuation(inputs)


def test_scores_clamped() -> None:
    snap = evaluate_continuation(_inputs(_bullish_continuation(step=5.0)))
    for value in (
        snap.continuation_score,
        snap.pressure_score,
        snap.momentum_decay,
        snap.confidence,
    ):
        assert 0.0 <= value <= 100.0
