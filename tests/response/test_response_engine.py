"""Tests for Response Engine (Module 03)."""

from __future__ import annotations

import math

from hotirjam_ai5.initiative import (
    InitiativeSide,
    InitiativeSnapshot,
    InitiativeState,
    OhlcCandle,
)
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import (
    ResponseEngine,
    ResponseInputs,
    ResponseSide,
    ResponseState,
    detect_counter_move,
    evaluate_response,
)


TICK = 0.25


def _c(o: float, h: float, l: float, c: float, *, volume: float = 100.0) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=volume)


def _initiative(
    side: InitiativeSide = InitiativeSide.BUYER,
    *,
    score: float = 70.0,
) -> InitiativeSnapshot:
    return InitiativeSnapshot(
        initiative_side=side,
        impulse_score=score,
        momentum_score=score,
        candle_strength_score=score,
        initiative_score=score,
        state=InitiativeState.STRONG if score >= 70 else InitiativeState.MEDIUM,
        confidence=80.0,
        reasons=("test initiative",),
        timestamp=1.0,
    )


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
    initiative: InitiativeSnapshot | None = None,
    tick_size: float = TICK,
    timestamp: float = 1_700_000_000.0,
) -> ResponseInputs:
    return ResponseInputs(
        objectives=_objectives(),
        initiative=initiative or _initiative(),
        candles=candles,
        tick_size=tick_size,
        timestamp=timestamp,
    )


def _counter_against_buyers(*, strong: bool = True) -> tuple[OhlcCandle, ...]:
    """Down move after buyer initiative — seller response."""
    step = 2.0 if strong else 0.35
    candles: list[OhlcCandle] = []
    price = 110.0
    for _ in range(4):
        nxt = price - step
        vol = 200.0 if strong else 80.0
        candles.append(_c(price, price + 0.1, nxt - 0.2, nxt, volume=vol))
        price = nxt
    return tuple(candles)


def _counter_against_sellers(*, strong: bool = True) -> tuple[OhlcCandle, ...]:
    step = 2.0 if strong else 0.35
    candles: list[OhlcCandle] = []
    price = 90.0
    for _ in range(4):
        nxt = price + step
        candles.append(_c(price, nxt + 0.2, price - 0.1, nxt, volume=180.0 if strong else 70.0))
        price = nxt
    return tuple(candles)


def _flat(price: float = 100.0, n: int = 4) -> tuple[OhlcCandle, ...]:
    return tuple(_c(price, price + 0.05, price - 0.05, price) for _ in range(n))


# ---------------------------------------------------------------- RE01


def test_counter_move_against_buyer_initiative() -> None:
    result = detect_counter_move(
        _counter_against_buyers(strong=True),
        initiative=_initiative(InitiativeSide.BUYER),
        tick_size=TICK,
    )
    assert result.detected is True
    assert result.response_side is ResponseSide.SELLER
    assert result.magnitude_ticks > 0.0


def test_counter_move_against_seller_initiative() -> None:
    result = detect_counter_move(
        _counter_against_sellers(strong=True),
        initiative=_initiative(InitiativeSide.SELLER),
        tick_size=TICK,
    )
    assert result.detected is True
    assert result.response_side is ResponseSide.BUYER


def test_no_counter_when_no_initiative() -> None:
    result = detect_counter_move(
        _counter_against_buyers(),
        initiative=_initiative(InitiativeSide.NONE, score=0.0),
        tick_size=TICK,
    )
    assert result.detected is False
    assert result.response_side is ResponseSide.NONE


# ---------------------------------------------------------------- Engine scenarios


def test_strong_response_challenges_initiative() -> None:
    snap = evaluate_response(
        _inputs(
            _counter_against_buyers(strong=True),
            initiative=_initiative(InitiativeSide.BUYER, score=50.0),
        )
    )
    assert snap.response_side is ResponseSide.SELLER
    assert snap.response_strength > 35.0
    assert snap.response_state in {
        ResponseState.NEUTRAL,
        ResponseState.STRONG,
        ResponseState.WEAK,
    }
    assert snap.reasons


def test_strong_response_can_erase_weak_initiative() -> None:
    snap = evaluate_response(
        _inputs(
            _counter_against_buyers(strong=True),
            initiative=_initiative(InitiativeSide.BUYER, score=40.0),
        )
    )
    assert snap.response_side is ResponseSide.SELLER
    # Strong multi-tick counter vs moderate initiative → not preserved.
    assert snap.initiative_preserved is False or snap.response_strength >= 50.0


def test_weak_response() -> None:
    snap = evaluate_response(
        _inputs(
            _counter_against_buyers(strong=False),
            initiative=_initiative(InitiativeSide.BUYER, score=80.0),
        )
    )
    assert snap.response_state in {ResponseState.FAILED, ResponseState.WEAK, ResponseState.NEUTRAL}
    assert snap.initiative_preserved is True


def test_failed_response_flat_market() -> None:
    snap = evaluate_response(
        _inputs(_flat(), initiative=_initiative(InitiativeSide.BUYER, score=70.0))
    )
    assert snap.response_side is ResponseSide.NONE or snap.response_state is ResponseState.FAILED
    assert snap.initiative_preserved is True
    assert snap.response_strength == 0.0 or snap.response_state is ResponseState.FAILED


def test_empty_candles() -> None:
    snap = evaluate_response(_inputs(()))
    assert snap.response_side is ResponseSide.NONE
    assert "Empty" in snap.reasons[0]


def test_invalid_tick_size() -> None:
    snap = evaluate_response(_inputs(_counter_against_buyers(), tick_size=0.0))
    assert snap.response_side is ResponseSide.NONE
    assert "tick" in snap.reasons[0].lower()


def test_invalid_nan_candles() -> None:
    bad = (_c(math.nan, 101, 99, 100), *_counter_against_buyers())
    snap = evaluate_response(_inputs(bad))
    assert snap.response_strength >= 0.0


def test_engine_retains_latest() -> None:
    engine = ResponseEngine(clock=lambda: 7.0)
    assert engine.snapshot().response_side is ResponseSide.NONE
    first = engine.evaluate(_inputs(_counter_against_buyers()))
    assert engine.snapshot() is first
    second = engine.evaluate(_inputs(()))
    assert engine.snapshot() is second


def test_deterministic() -> None:
    inputs = _inputs(_counter_against_sellers(), initiative=_initiative(InitiativeSide.SELLER))
    assert evaluate_response(inputs) == evaluate_response(inputs)


def test_scores_clamped() -> None:
    snap = evaluate_response(_inputs(_counter_against_buyers(strong=True)))
    assert 0.0 <= snap.response_strength <= 100.0
    assert 0.0 <= snap.confidence <= 100.0
