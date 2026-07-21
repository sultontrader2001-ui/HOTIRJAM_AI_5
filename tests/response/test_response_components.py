"""Component-level tests for Response Engine submodules."""

from __future__ import annotations

from hotirjam_ai5.initiative import (
    InitiativeSide,
    InitiativeSnapshot,
    InitiativeState,
    OhlcCandle,
)
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import (
    CounterMoveResult,
    ResponseSide,
    ResponseState,
    ResponseStrengthResult,
    analyze_response_strength,
    detect_counter_move,
    evaluate_initiative_preservation,
    score_response,
)
from hotirjam_ai5.response.response_models import InitiativePreservationResult


def _c(o: float, h: float, l: float, c: float, *, volume: float = 100.0) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=volume)


def _initiative(side: InitiativeSide, score: float = 70.0) -> InitiativeSnapshot:
    return InitiativeSnapshot(
        initiative_side=side,
        impulse_score=score,
        momentum_score=score,
        candle_strength_score=score,
        initiative_score=score,
        state=InitiativeState.MEDIUM,
        confidence=50.0,
        reasons=(),
        timestamp=1.0,
    )


def test_strength_zero_without_counter() -> None:
    result = analyze_response_strength(
        (_c(100, 101, 99, 100.5),),
        initiative=_initiative(InitiativeSide.BUYER),
        counter=CounterMoveResult(False, ResponseSide.NONE, 0.0, ("none",)),
        tick_size=0.25,
    )
    assert result.strength == 0.0


def test_preservation_true_without_counter() -> None:
    result = evaluate_initiative_preservation(
        initiative=_initiative(InitiativeSide.BUYER, 80.0),
        counter=CounterMoveResult(False, ResponseSide.NONE, 0.0, ()),
        strength=ResponseStrengthResult(0.0, ()),
    )
    assert result.preserved is True


def test_preservation_false_on_strong_counter() -> None:
    result = evaluate_initiative_preservation(
        initiative=_initiative(InitiativeSide.BUYER, 40.0),
        counter=CounterMoveResult(True, ResponseSide.SELLER, 12.0, ()),
        strength=ResponseStrengthResult(85.0, ()),
    )
    assert result.preserved is False


def test_scorer_failed_state() -> None:
    snap = score_response(
        counter=CounterMoveResult(False, ResponseSide.NONE, 0.0, ("no move",)),
        strength=ResponseStrengthResult(0.0, ("none",)),
        preservation=InitiativePreservationResult(True, ("ok",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=5.0,
    )
    assert snap.response_state is ResponseState.FAILED
    assert snap.initiative_preserved is True
    assert snap.timestamp == 5.0


def test_scorer_strong_state() -> None:
    snap = score_response(
        counter=CounterMoveResult(True, ResponseSide.BUYER, 15.0, ("detected",)),
        strength=ResponseStrengthResult(80.0, ("strong",)),
        preservation=InitiativePreservationResult(False, ("lost",)),
        objectives=ObjectiveSnapshot(
            nearest_high_price=105.0,
            nearest_high_distance_ticks=20.0,
            nearest_high_strength=50.0,
            nearest_low_price=95.0,
            nearest_low_distance_ticks=20.0,
            nearest_low_strength=50.0,
            current_price=100.0,
            timestamp=1.0,
        ),
        timestamp=1.0,
    )
    assert snap.response_state is ResponseState.STRONG
    assert snap.response_side is ResponseSide.BUYER
    assert snap.initiative_preserved is False
    assert snap.confidence > 50.0


def test_detect_insufficient_candles() -> None:
    result = detect_counter_move(
        (_c(100, 101, 99, 100.5),),
        initiative=_initiative(InitiativeSide.SELLER),
        tick_size=0.25,
    )
    assert result.detected is False


def test_detect_invalid_tick() -> None:
    result = detect_counter_move(
        (_c(100, 101, 99, 100.5), _c(100.5, 101, 99, 99.0)),
        initiative=_initiative(InitiativeSide.BUYER),
        tick_size=-0.25,
    )
    assert result.detected is False


def test_strength_invalid_tick_and_empty() -> None:
    counter = CounterMoveResult(True, ResponseSide.SELLER, 5.0, ("ok",))
    assert (
        analyze_response_strength(
            (_c(100, 101, 99, 99),),
            initiative=_initiative(InitiativeSide.BUYER),
            counter=counter,
            tick_size=0.0,
        ).strength
        == 0.0
    )
    assert (
        analyze_response_strength(
            (),
            initiative=_initiative(InitiativeSide.BUYER),
            counter=counter,
            tick_size=0.25,
        ).strength
        == 0.0
    )


def test_strength_without_volume() -> None:
    candles = (
        _c(110, 110.2, 108, 108.5, volume=0.0),
        _c(108.5, 108.6, 106, 106.5, volume=0.0),
        _c(106.5, 106.6, 104, 104.5, volume=0.0),
        _c(104.5, 104.6, 102, 102.5, volume=0.0),
    )
    counter = detect_counter_move(
        candles,
        initiative=_initiative(InitiativeSide.BUYER),
        tick_size=0.25,
    )
    strength = analyze_response_strength(
        candles,
        initiative=_initiative(InitiativeSide.BUYER),
        counter=counter,
        tick_size=0.25,
    )
    assert strength.strength >= 0.0


def test_preservation_no_initiative_and_material_challenge() -> None:
    none_init = evaluate_initiative_preservation(
        initiative=_initiative(InitiativeSide.NONE, 0.0),
        counter=CounterMoveResult(True, ResponseSide.SELLER, 5.0, ()),
        strength=ResponseStrengthResult(50.0, ()),
    )
    assert none_init.preserved is True

    material = evaluate_initiative_preservation(
        initiative=_initiative(InitiativeSide.BUYER, 90.0),
        counter=CounterMoveResult(True, ResponseSide.SELLER, 10.0, ()),
        strength=ResponseStrengthResult(55.0, ()),
    )
    assert material.preserved is False


def test_scorer_weak_state() -> None:
    snap = score_response(
        counter=CounterMoveResult(True, ResponseSide.SELLER, 3.0, ("detected",)),
        strength=ResponseStrengthResult(25.0, ("weak",)),
        preservation=InitiativePreservationResult(True, ("held",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=1.0,
    )
    assert snap.response_state is ResponseState.WEAK
