"""Tests for Break Capability Engine (Module 05)."""

from __future__ import annotations

from hotirjam_ai5.break_capability import (
    BreakCapabilityEngine,
    BreakCapabilityInputs,
    BreakCapabilityState,
    TargetSide,
    TargetType,
    evaluate_break_capability,
    evaluate_resistance,
    measure_objective_pressure,
)
from hotirjam_ai5.continuation import (
    ContinuationSide,
    ContinuationSnapshot,
    ContinuationState,
)
from hotirjam_ai5.initiative import (
    InitiativeSide,
    InitiativeSnapshot,
    InitiativeState,
)
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSide, ResponseSnapshot, ResponseState


def _objectives(
    *,
    high_dist: float = 8.0,
    low_dist: float = 20.0,
    high_str: float = 40.0,
    low_str: float = 60.0,
    complete: bool = True,
) -> ObjectiveSnapshot:
    if not complete:
        return ObjectiveSnapshot.empty(timestamp=1.0, current_price=100.0)
    return ObjectiveSnapshot(
        nearest_high_price=102.0,
        nearest_high_distance_ticks=high_dist,
        nearest_high_strength=high_str,
        nearest_low_price=95.0,
        nearest_low_distance_ticks=low_dist,
        nearest_low_strength=low_str,
        current_price=100.0,
        timestamp=1.0,
    )


def _initiative(
    side: InitiativeSide = InitiativeSide.BUYER,
    *,
    score: float = 80.0,
    state: InitiativeState | None = None,
) -> InitiativeSnapshot:
    if state is None:
        if score >= 70:
            state = InitiativeState.STRONG
        elif score >= 35:
            state = InitiativeState.MEDIUM
        else:
            state = InitiativeState.WEAK
    return InitiativeSnapshot(
        initiative_side=side,
        impulse_score=score,
        momentum_score=score,
        candle_strength_score=score,
        initiative_score=score,
        state=state,
        confidence=70.0,
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
        reasons=("test",),
        timestamp=1.0,
    )


def _continuation(
    side: ContinuationSide = ContinuationSide.BUYER,
    *,
    score: float = 80.0,
    pressure: float = 80.0,
    decay: float = 15.0,
    state: ContinuationState | None = None,
) -> ContinuationSnapshot:
    if state is None:
        if score >= 70:
            state = ContinuationState.STRONG
        elif score >= 35:
            state = ContinuationState.MEDIUM
        else:
            state = ContinuationState.WEAK
    return ContinuationSnapshot(
        continuation_side=side,
        continuation_score=score,
        pressure_score=pressure,
        momentum_decay=decay,
        state=state,
        confidence=70.0,
        reasons=("test",),
        timestamp=1.0,
    )


def _inputs(
    *,
    objectives: ObjectiveSnapshot | None = None,
    initiative: InitiativeSnapshot | None = None,
    response: ResponseSnapshot | None = None,
    continuation: ContinuationSnapshot | None = None,
) -> BreakCapabilityInputs:
    return BreakCapabilityInputs(
        objectives=objectives or _objectives(),
        initiative=initiative or _initiative(),
        response=response or _response(),
        continuation=continuation or _continuation(),
        timestamp=1_700_000_000.0,
    )


# ---------------------------------------------------------------- BK01 / BK02


def test_pressure_toward_high_for_buyers() -> None:
    result = measure_objective_pressure(
        objectives=_objectives(high_dist=5.0, high_str=40.0),
        initiative=_initiative(InitiativeSide.BUYER, score=85.0),
        response=_response(preserved=True, state=ResponseState.FAILED),
        continuation=_continuation(ContinuationSide.BUYER, score=85.0, pressure=85.0),
    )
    assert result.target_side is TargetSide.BUYER
    assert result.target_type is TargetType.HIGH
    assert result.pressure_score > 50.0


def test_pressure_toward_low_for_sellers() -> None:
    result = measure_objective_pressure(
        objectives=_objectives(low_dist=5.0, low_str=40.0),
        initiative=_initiative(InitiativeSide.SELLER, score=85.0),
        response=_response(preserved=True, state=ResponseState.FAILED),
        continuation=_continuation(ContinuationSide.SELLER, score=85.0, pressure=85.0),
    )
    assert result.target_side is TargetSide.SELLER
    assert result.target_type is TargetType.LOW
    assert result.pressure_score > 50.0


def test_resistance_higher_for_strong_far_objective() -> None:
    pressure = measure_objective_pressure(
        objectives=_objectives(high_dist=30.0, high_str=90.0),
        initiative=_initiative(score=70.0),
        response=_response(),
        continuation=_continuation(score=70.0, pressure=70.0),
    )
    high_res = evaluate_resistance(
        objectives=_objectives(high_dist=30.0, high_str=90.0),
        pressure=pressure,
        response=_response(state=ResponseState.STRONG, strength=80.0, preserved=False),
    )
    low_res = evaluate_resistance(
        objectives=_objectives(high_dist=4.0, high_str=25.0),
        pressure=pressure,
        response=_response(state=ResponseState.FAILED, preserved=True),
    )
    assert high_res.resistance_score > low_res.resistance_score


# ---------------------------------------------------------------- Engine scenarios


def test_high_breakout_probability() -> None:
    snap = evaluate_break_capability(
        _inputs(
            objectives=_objectives(high_dist=4.0, high_str=25.0),
            initiative=_initiative(score=90.0, state=InitiativeState.STRONG),
            response=_response(preserved=True, state=ResponseState.FAILED),
            continuation=_continuation(
                score=90.0,
                pressure=90.0,
                decay=10.0,
                state=ContinuationState.STRONG,
            ),
        )
    )
    assert snap.target_side is TargetSide.BUYER
    assert snap.target_type is TargetType.HIGH
    assert snap.break_probability > 55.0
    assert snap.state in {BreakCapabilityState.MEDIUM, BreakCapabilityState.HIGH}
    assert snap.reasons


def test_low_breakout_probability() -> None:
    snap = evaluate_break_capability(
        _inputs(
            objectives=_objectives(high_dist=35.0, high_str=90.0),
            initiative=_initiative(score=25.0, state=InitiativeState.WEAK),
            response=_response(preserved=False, state=ResponseState.STRONG, strength=80.0),
            continuation=_continuation(
                score=20.0,
                pressure=20.0,
                decay=85.0,
                state=ContinuationState.WEAK,
            ),
        )
    )
    assert snap.break_probability < 45.0
    assert snap.state is BreakCapabilityState.LOW


def test_flat_market_no_side() -> None:
    snap = evaluate_break_capability(
        _inputs(
            initiative=_initiative(InitiativeSide.NONE, score=0.0),
            continuation=_continuation(ContinuationSide.NONE, score=0.0, pressure=0.0),
        )
    )
    assert snap.target_side is TargetSide.NONE
    assert snap.target_type is TargetType.NONE
    assert snap.break_probability == 0.0
    assert snap.state is BreakCapabilityState.LOW


def test_strong_initiative_but_failed_response_context() -> None:
    """Strong initiative + failed opposing response supports break capability."""
    snap = evaluate_break_capability(
        _inputs(
            objectives=_objectives(high_dist=10.0, high_str=45.0),
            initiative=_initiative(score=85.0, state=InitiativeState.STRONG),
            response=_response(preserved=True, state=ResponseState.FAILED),
            continuation=_continuation(score=75.0, pressure=75.0, decay=20.0),
        )
    )
    challenged = evaluate_break_capability(
        _inputs(
            objectives=_objectives(high_dist=10.0, high_str=45.0),
            initiative=_initiative(score=85.0, state=InitiativeState.STRONG),
            response=_response(preserved=False, state=ResponseState.STRONG, strength=80.0),
            continuation=_continuation(score=75.0, pressure=75.0, decay=20.0),
        )
    )
    assert snap.break_probability > challenged.break_probability


def test_weak_initiative() -> None:
    snap = evaluate_break_capability(
        _inputs(
            initiative=_initiative(score=20.0, state=InitiativeState.WEAK),
            continuation=_continuation(
                score=25.0,
                pressure=25.0,
                decay=70.0,
                state=ContinuationState.WEAK,
            ),
            response=_response(preserved=True, state=ResponseState.WEAK, strength=30.0),
        )
    )
    assert snap.break_probability < 60.0
    assert snap.pressure_score < 55.0


def test_incomplete_objectives() -> None:
    snap = evaluate_break_capability(
        _inputs(objectives=_objectives(complete=False))
    )
    assert snap.break_probability == 0.0
    assert snap.target_type is TargetType.NONE


def test_engine_retains_latest() -> None:
    engine = BreakCapabilityEngine(clock=lambda: 11.0)
    assert engine.snapshot().target_side is TargetSide.NONE
    first = engine.evaluate(_inputs())
    assert engine.snapshot() is first
    second = engine.evaluate(
        _inputs(
            initiative=_initiative(InitiativeSide.NONE, score=0.0),
            continuation=_continuation(ContinuationSide.NONE, score=0.0),
        )
    )
    assert engine.snapshot() is second


def test_deterministic() -> None:
    inputs = _inputs()
    assert evaluate_break_capability(inputs) == evaluate_break_capability(inputs)


def test_scores_clamped() -> None:
    snap = evaluate_break_capability(_inputs())
    for value in (
        snap.break_probability,
        snap.pressure_score,
        snap.resistance_score,
        snap.confidence,
    ):
        assert 0.0 <= value <= 100.0
