"""Tests for Initiative Engine (Module 02)."""

from __future__ import annotations

import math

from hotirjam_ai5.initiative import (
    ImpulseSide,
    InitiativeEngine,
    InitiativeInputs,
    InitiativeSide,
    InitiativeState,
    MomentumState,
    OhlcCandle,
    analyze_candle_strength,
    detect_impulse,
    detect_momentum,
    evaluate_initiative,
)
from hotirjam_ai5.objective import ObjectiveSnapshot


TICK = 0.25


def _c(
    o: float,
    h: float,
    l: float,
    c: float,
    *,
    volume: float = 100.0,
) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=volume)


def _bullish_run(start: float = 100.0, steps: int = 5, step: float = 1.0) -> tuple[OhlcCandle, ...]:
    candles: list[OhlcCandle] = []
    price = start
    for _ in range(steps):
        nxt = price + step
        candles.append(_c(price, nxt + 0.25, price - 0.1, nxt))
        price = nxt
    return tuple(candles)


def _bearish_run(start: float = 100.0, steps: int = 5, step: float = 1.0) -> tuple[OhlcCandle, ...]:
    candles: list[OhlcCandle] = []
    price = start
    for _ in range(steps):
        nxt = price - step
        candles.append(_c(price, price + 0.1, nxt - 0.25, nxt))
        price = nxt
    return tuple(candles)


def _flat(price: float = 100.0, n: int = 5) -> tuple[OhlcCandle, ...]:
    return tuple(_c(price, price + 0.1, price - 0.1, price) for _ in range(n))


def _objectives(*, price: float = 100.0, complete: bool = True) -> ObjectiveSnapshot:
    if not complete:
        return ObjectiveSnapshot.empty(timestamp=1.0, current_price=price)
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


def _inputs(
    candles: tuple[OhlcCandle, ...],
    *,
    tick_size: float = TICK,
    timestamp: float = 1_700_000_000.0,
    objectives: ObjectiveSnapshot | None = None,
) -> InitiativeInputs:
    return InitiativeInputs(
        objectives=objectives or _objectives(),
        candles=candles,
        tick_size=tick_size,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------- IN01 Impulse


def test_impulse_detects_buy() -> None:
    result = detect_impulse(_bullish_run(), tick_size=TICK)
    assert result.side is ImpulseSide.BUY
    assert result.score > 0.0


def test_impulse_detects_sell() -> None:
    result = detect_impulse(_bearish_run(), tick_size=TICK)
    assert result.side is ImpulseSide.SELL
    assert result.score > 0.0


def test_impulse_none_on_flat() -> None:
    result = detect_impulse(_flat(), tick_size=TICK)
    assert result.side is ImpulseSide.NONE
    assert result.score == 0.0


# ---------------------------------------------------------------- IN02 Momentum


def test_momentum_accelerating_up() -> None:
    # Slow then fast upward.
    candles = (
        _c(100.0, 100.3, 99.9, 100.25),
        _c(100.25, 100.5, 100.1, 100.4),
        _c(100.4, 100.6, 100.3, 100.5),
        _c(100.5, 101.5, 100.4, 101.4),
        _c(101.4, 102.5, 101.3, 102.4),
        _c(102.4, 103.5, 102.3, 103.4),
    )
    result = detect_momentum(candles, tick_size=TICK)
    assert result.direction is ImpulseSide.BUY
    assert result.score > 0.0
    assert result.state in {MomentumState.MEDIUM, MomentumState.HIGH, MomentumState.LOW}


def test_momentum_low_on_flat() -> None:
    result = detect_momentum(_flat(n=6), tick_size=TICK)
    assert result.state is MomentumState.LOW
    assert result.direction is ImpulseSide.NONE


# ---------------------------------------------------------------- IN03 Candle strength


def test_candle_strength_strong_bullish() -> None:
    candles = _bullish_run(step=2.0)
    result = analyze_candle_strength(candles)
    assert result.direction is ImpulseSide.BUY
    assert result.score > 40.0


def test_candle_strength_weak_doji_like() -> None:
    # Tiny bodies + mixed direction → weak body contribution / no dominant side.
    candles = (
        _c(100.0, 100.5, 99.5, 100.02),
        _c(100.0, 100.5, 99.5, 99.98),
        _c(100.0, 100.5, 99.5, 100.01),
        _c(100.0, 100.5, 99.5, 99.99),
        _c(100.0, 100.5, 99.5, 100.0),
    )
    result = analyze_candle_strength(candles)
    assert result.score < 50.0
    assert "Body ratio" in result.reasons[0]


# ---------------------------------------------------------------- IN04 / Engine scoring


def test_initiative_buyer_on_bullish_impulse() -> None:
    snap = evaluate_initiative(_inputs(_bullish_run(step=1.5)))
    assert snap.initiative_side is InitiativeSide.BUYER
    assert snap.initiative_score > 0.0
    assert snap.state in {InitiativeState.WEAK, InitiativeState.MEDIUM, InitiativeState.STRONG}
    assert 0.0 <= snap.confidence <= 100.0
    assert snap.reasons


def test_initiative_seller_on_bearish_impulse() -> None:
    snap = evaluate_initiative(_inputs(_bearish_run(step=1.5)))
    assert snap.initiative_side is InitiativeSide.SELLER
    assert snap.impulse_score > 0.0
    assert snap.momentum_score >= 0.0
    assert snap.candle_strength_score >= 0.0


def test_flat_market_yields_none() -> None:
    snap = evaluate_initiative(_inputs(_flat(n=6)))
    assert snap.initiative_side is InitiativeSide.NONE
    assert snap.state is InitiativeState.WEAK


# ---------------------------------------------------------------- Invalid / empty / extremes


def test_empty_candles() -> None:
    snap = evaluate_initiative(_inputs(()))
    assert snap.initiative_side is InitiativeSide.NONE
    assert snap.initiative_score == 0.0
    assert "Empty" in snap.reasons[0]


def test_invalid_tick_size() -> None:
    snap = evaluate_initiative(_inputs(_bullish_run(), tick_size=0.0))
    assert snap.initiative_side is InitiativeSide.NONE
    assert "tick" in snap.reasons[0].lower()


def test_invalid_nan_candles_ignored() -> None:
    bad = (
        _c(math.nan, 101.0, 99.0, 100.0),
        *_bullish_run(step=1.5),
    )
    snap = evaluate_initiative(_inputs(bad))
    # Still evaluates from valid subset.
    assert snap.impulse_score >= 0.0


def test_extreme_volatility() -> None:
    candles = _bullish_run(start=100.0, steps=6, step=25.0)
    snap = evaluate_initiative(_inputs(candles))
    assert snap.initiative_side is InitiativeSide.BUYER
    assert snap.impulse_score == 100.0 or snap.impulse_score > 80.0
    assert snap.initiative_score <= 100.0


def test_incomplete_objectives_still_evaluate() -> None:
    snap = evaluate_initiative(
        _inputs(_bullish_run(step=1.5), objectives=_objectives(complete=False))
    )
    assert snap.initiative_side is InitiativeSide.BUYER


def test_engine_retains_latest() -> None:
    engine = InitiativeEngine(clock=lambda: 42.0)
    assert engine.snapshot().initiative_side is InitiativeSide.NONE
    first = engine.evaluate(_inputs(_bullish_run(step=1.5)))
    assert engine.snapshot() is first
    second = engine.evaluate(_inputs(()))
    assert engine.snapshot() is second
    assert second.initiative_side is InitiativeSide.NONE


def test_deterministic() -> None:
    inputs = _inputs(_bearish_run(step=1.25))
    assert evaluate_initiative(inputs) == evaluate_initiative(inputs)


def test_scores_clamped_0_100() -> None:
    snap = evaluate_initiative(_inputs(_bullish_run(steps=6, step=50.0)))
    for value in (
        snap.impulse_score,
        snap.momentum_score,
        snap.candle_strength_score,
        snap.initiative_score,
        snap.confidence,
    ):
        assert 0.0 <= value <= 100.0
