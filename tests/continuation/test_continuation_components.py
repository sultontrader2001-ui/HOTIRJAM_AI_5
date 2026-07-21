"""Component-level tests for Continuation Engine submodules."""

from __future__ import annotations

from hotirjam_ai5.continuation import (
    ContinuationSide,
    ContinuationState,
    ContinuationStrengthResult,
    MomentumDecayResult,
    PressurePersistenceResult,
    measure_continuation_strength,
    measure_momentum_decay,
    measure_pressure_persistence,
    score_continuation,
)
from hotirjam_ai5.initiative import (
    InitiativeEvidence,
    InitiativeSide,
    InitiativeSnapshot,
    InitiativeState,
    OhlcCandle,
)
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSide, ResponseSnapshot, ResponseState


def _c(o: float, h: float, l: float, c: float) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=50.0)


def _initiative(
    side: InitiativeSide = InitiativeSide.BUYER,
    score: float = 70.0,
    *,
    state: InitiativeState | None = None,
) -> InitiativeSnapshot:
    if state is None:
        if score >= 70:
            state = InitiativeState.DOMINANT
        elif score >= 35:
            state = InitiativeState.EMERGING
        elif score > 0:
            state = InitiativeState.WEAKENING
        else:
            state = InitiativeState.NONE
    buyer = (
        score
        if side is InitiativeSide.BUYER
        else (0.0 if side is InitiativeSide.NONE else max(0.0, score - 30.0))
    )
    seller = (
        score
        if side is InitiativeSide.SELLER
        else (0.0 if side is InitiativeSide.NONE else max(0.0, score - 30.0))
    )
    if side is InitiativeSide.NONE:
        buyer = seller = 0.0
    return InitiativeSnapshot(
        buyer_initiative=buyer,
        seller_initiative=seller,
        dominant_side=side,
        initiative_state=state,
        confidence=80.0,
        evidence=InitiativeEvidence(score, score, score, score, score, 0.0),
        reasons=("test initiative",),
        timestamp=1.0,
    )


def _response() -> ResponseSnapshot:
    return ResponseSnapshot(
        response_side=ResponseSide.NONE,
        response_strength=0.0,
        response_state=ResponseState.FAILED,
        initiative_preserved=True,
        confidence=40.0,
        reasons=(),
        timestamp=1.0,
    )


def test_pressure_no_initiative() -> None:
    result = measure_pressure_persistence(
        (_c(100, 101, 99, 100.5), _c(100.5, 101, 100, 100.8)),
        initiative=_initiative(InitiativeSide.NONE, 0.0),
        response=_response(),
        tick_size=0.25,
    )
    assert result.pressure_score == 0.0


def test_decay_invalid_tick() -> None:
    result = measure_momentum_decay(
        (_c(100, 101, 99, 100.5),) * 4,
        initiative=_initiative(InitiativeSide.BUYER),
        tick_size=0.0,
    )
    assert result.momentum_decay == 100.0


def test_continuation_strength_supports_buyers() -> None:
    candles = (
        _c(100, 101.5, 99.9, 101.4),
        _c(101.4, 102.5, 101.2, 102.4),
        _c(102.4, 103.5, 102.2, 103.4),
        _c(103.4, 104.5, 103.2, 104.4),
        _c(104.4, 105.5, 104.2, 105.4),
    )
    result = measure_continuation_strength(
        candles,
        initiative=_initiative(InitiativeSide.BUYER),
    )
    assert result.strength_score > 50.0


def test_continuation_strength_empty() -> None:
    result = measure_continuation_strength((), initiative=_initiative(InitiativeSide.SELLER))
    assert result.strength_score == 0.0


def test_scorer_strong() -> None:
    snap = score_continuation(
        initiative=_initiative(InitiativeSide.BUYER, 80.0),
        pressure=PressurePersistenceResult(85.0, ("p",)),
        decay=MomentumDecayResult(15.0, ("d",)),
        strength=ContinuationStrengthResult(80.0, ("s",)),
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
        timestamp=9.0,
    )
    assert snap.continuation_side is ContinuationSide.BUYER
    assert snap.state is ContinuationState.STRONG
    assert snap.timestamp == 9.0
    assert snap.confidence >= 100.0 or snap.confidence >= 95.0


def test_scorer_clears_side_when_very_weak() -> None:
    snap = score_continuation(
        initiative=_initiative(InitiativeSide.SELLER, 40.0),
        pressure=PressurePersistenceResult(5.0, ("p",)),
        decay=MomentumDecayResult(95.0, ("d",)),
        strength=ContinuationStrengthResult(5.0, ("s",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=1.0,
    )
    assert snap.continuation_side is ContinuationSide.NONE
    assert snap.state is ContinuationState.WEAK


def test_scorer_seller_side_and_medium_state() -> None:
    snap = score_continuation(
        initiative=_initiative(InitiativeSide.SELLER, 60.0),
        pressure=PressurePersistenceResult(55.0, ("p",)),
        decay=MomentumDecayResult(40.0, ("d",)),
        strength=ContinuationStrengthResult(50.0, ("s",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=1.0,
    )
    assert snap.continuation_side is ContinuationSide.SELLER
    assert snap.state is ContinuationState.MEDIUM


def test_pressure_invalid_and_insufficient() -> None:
    assert (
        measure_pressure_persistence(
            (_c(100, 101, 99, 100),) * 3,
            initiative=_initiative(InitiativeSide.BUYER),
            response=_response(),
            tick_size=0.0,
        ).pressure_score
        == 0.0
    )
    assert (
        measure_pressure_persistence(
            (_c(100, 101, 99, 100),),
            initiative=_initiative(InitiativeSide.BUYER),
            response=_response(),
            tick_size=0.25,
        ).pressure_score
        == 0.0
    )


def test_pressure_seller_and_response_states() -> None:
    down = (
        _c(110, 110.2, 108.5, 108.6),
        _c(108.6, 108.8, 107.0, 107.1),
        _c(107.1, 107.3, 105.5, 105.6),
        _c(105.6, 105.8, 104.0, 104.1),
        _c(104.1, 104.3, 102.5, 102.6),
    )
    strong_resp = ResponseSnapshot(
        response_side=ResponseSide.BUYER,
        response_strength=70.0,
        response_state=ResponseState.STRONG,
        initiative_preserved=True,
        confidence=50.0,
        reasons=(),
        timestamp=1.0,
    )
    weak_resp = ResponseSnapshot(
        response_side=ResponseSide.BUYER,
        response_strength=30.0,
        response_state=ResponseState.WEAK,
        initiative_preserved=True,
        confidence=50.0,
        reasons=(),
        timestamp=1.0,
    )
    a = measure_pressure_persistence(
        down,
        initiative=_initiative(InitiativeSide.SELLER, 70.0),
        response=strong_resp,
        tick_size=0.25,
    )
    b = measure_pressure_persistence(
        down,
        initiative=_initiative(InitiativeSide.SELLER, 70.0),
        response=weak_resp,
        tick_size=0.25,
    )
    assert a.pressure_score < b.pressure_score


def test_decay_insufficient_candles() -> None:
    result = measure_momentum_decay(
        (_c(100, 101, 99, 100.5), _c(100.5, 101, 100, 100.8), _c(100.8, 101, 100, 100.9)),
        initiative=_initiative(InitiativeSide.BUYER),
        tick_size=0.25,
    )
    assert result.momentum_decay == 100.0
