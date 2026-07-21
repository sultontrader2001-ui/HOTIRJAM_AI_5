"""Component-level tests for Break Capability submodules."""

from __future__ import annotations

from hotirjam_ai5.break_capability import (
    BreakCapabilityState,
    EvidenceAggregatorResult,
    ObjectivePressureResult,
    ResistanceEvaluationResult,
    TargetSide,
    TargetType,
    aggregate_break_evidence,
    evaluate_resistance,
    measure_objective_pressure,
    score_break_capability,
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


def _objectives(**kwargs: float) -> ObjectiveSnapshot:
    return ObjectiveSnapshot(
        nearest_high_price=102.0,
        nearest_high_distance_ticks=kwargs.get("high_dist", 10.0),
        nearest_high_strength=kwargs.get("high_str", 50.0),
        nearest_low_price=95.0,
        nearest_low_distance_ticks=kwargs.get("low_dist", 10.0),
        nearest_low_strength=kwargs.get("low_str", 50.0),
        current_price=100.0,
        timestamp=1.0,
    )


def _initiative(side: InitiativeSide = InitiativeSide.BUYER, score: float = 70.0) -> InitiativeSnapshot:
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


def _response(
    *,
    preserved: bool = True,
    state: ResponseState = ResponseState.FAILED,
) -> ResponseSnapshot:
    return ResponseSnapshot(
        response_side=ResponseSide.NONE,
        response_strength=0.0,
        response_state=state,
        initiative_preserved=preserved,
        confidence=40.0,
        reasons=(),
        timestamp=1.0,
    )


def _continuation(
    side: ContinuationSide = ContinuationSide.BUYER,
    *,
    score: float = 70.0,
) -> ContinuationSnapshot:
    return ContinuationSnapshot(
        continuation_side=side,
        continuation_score=score,
        pressure_score=score,
        momentum_decay=20.0,
        state=ContinuationState.MEDIUM,
        confidence=50.0,
        reasons=(),
        timestamp=1.0,
    )


def test_pressure_none_without_side() -> None:
    result = measure_objective_pressure(
        objectives=_objectives(),
        initiative=_initiative(InitiativeSide.NONE, 0.0),
        response=_response(),
        continuation=_continuation(ContinuationSide.NONE, score=0.0),
    )
    assert result.pressure_score == 0.0
    assert result.target_type is TargetType.NONE


def test_resistance_none_target() -> None:
    result = evaluate_resistance(
        objectives=_objectives(),
        pressure=ObjectivePressureResult(0.0, TargetSide.NONE, TargetType.NONE, ()),
        response=_response(),
    )
    assert result.resistance_score == 0.0


def test_evidence_zero_without_target() -> None:
    result = aggregate_break_evidence(
        pressure=ObjectivePressureResult(0.0, TargetSide.NONE, TargetType.NONE, ()),
        resistance=ResistanceEvaluationResult(0.0, ()),
        initiative=_initiative(),
        response=_response(),
        continuation=_continuation(),
    )
    assert result.break_probability == 0.0


def test_scorer_high_state() -> None:
    snap = score_break_capability(
        pressure=ObjectivePressureResult(90.0, TargetSide.BUYER, TargetType.HIGH, ("p",)),
        resistance=ResistanceEvaluationResult(20.0, ("r",)),
        evidence=EvidenceAggregatorResult(85.0, ("a",)),
        objectives=_objectives(),
        timestamp=42.0,
    )
    assert snap.state is BreakCapabilityState.HIGH
    assert snap.target_side is TargetSide.BUYER
    assert snap.timestamp == 42.0
    assert snap.confidence > 50.0


def test_scorer_low_when_no_target() -> None:
    snap = score_break_capability(
        pressure=ObjectivePressureResult(0.0, TargetSide.NONE, TargetType.NONE, ("none",)),
        resistance=ResistanceEvaluationResult(0.0, ()),
        evidence=EvidenceAggregatorResult(0.0, ()),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=1.0,
    )
    assert snap.state is BreakCapabilityState.LOW
    assert snap.break_probability == 0.0


def test_response_state_branches_in_resistance() -> None:
    pressure = ObjectivePressureResult(60.0, TargetSide.BUYER, TargetType.HIGH, ())
    neutral = evaluate_resistance(
        objectives=_objectives(high_dist=10.0, high_str=50.0),
        pressure=pressure,
        response=_response(state=ResponseState.NEUTRAL),
    )
    weak = evaluate_resistance(
        objectives=_objectives(high_dist=10.0, high_str=50.0),
        pressure=pressure,
        response=_response(state=ResponseState.WEAK),
    )
    assert neutral.resistance_score >= weak.resistance_score
