"""BK04 — Break Capability Scorer.

Assembles the final BreakCapabilitySnapshot. No trade decisions.
"""

from __future__ import annotations

from hotirjam_ai5.break_capability.break_models import (
    BreakCapabilityState,
    EvidenceAggregatorResult,
    ObjectivePressureResult,
    ResistanceEvaluationResult,
    TargetSide,
    TargetType,
)
from hotirjam_ai5.break_capability.break_snapshot import BreakCapabilitySnapshot
from hotirjam_ai5.objective import ObjectiveSnapshot


def _state_from_probability(probability: float) -> BreakCapabilityState:
    if probability < 35.0:
        return BreakCapabilityState.LOW
    if probability < 70.0:
        return BreakCapabilityState.MEDIUM
    return BreakCapabilityState.HIGH


def score_break_capability(
    *,
    pressure: ObjectivePressureResult,
    resistance: ResistanceEvaluationResult,
    evidence: EvidenceAggregatorResult,
    objectives: ObjectiveSnapshot,
    timestamp: float,
) -> BreakCapabilitySnapshot:
    """Produce BreakCapabilitySnapshot from BK01–BK03."""
    reasons: list[str] = []
    reasons.extend(pressure.reasons)
    reasons.extend(resistance.reasons)
    reasons.extend(evidence.reasons)

    side = pressure.target_side
    target = pressure.target_type
    probability = evidence.break_probability

    if target is TargetType.NONE or side is TargetSide.NONE:
        return BreakCapabilitySnapshot(
            target_side=TargetSide.NONE,
            target_type=TargetType.NONE,
            break_probability=0.0,
            pressure_score=pressure.pressure_score,
            resistance_score=resistance.resistance_score,
            state=BreakCapabilityState.LOW,
            confidence=0.0,
            reasons=tuple(reasons) if reasons else ("No break target",),
            timestamp=timestamp,
        )

    state = _state_from_probability(probability)

    gap = abs(pressure.pressure_score - resistance.resistance_score)
    confidence = min(100.0, 40.0 + gap * 0.5)
    if objectives.is_complete:
        confidence = min(100.0, confidence + 10.0)
        reasons.append("Complete objectives — confidence reinforced")
    if probability < 15.0 or probability > 85.0:
        confidence = min(100.0, confidence + 5.0)

    return BreakCapabilitySnapshot(
        target_side=side,
        target_type=target,
        break_probability=probability,
        pressure_score=pressure.pressure_score,
        resistance_score=resistance.resistance_score,
        state=state,
        confidence=confidence,
        reasons=tuple(reasons),
        timestamp=timestamp,
    )
