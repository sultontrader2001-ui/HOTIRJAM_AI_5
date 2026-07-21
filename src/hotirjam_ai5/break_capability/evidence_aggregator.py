"""BK03 — Evidence Aggregator.

Combines Objective, Initiative, Response, Continuation, pressure, and resistance
into a unified breakout-capability assessment (break_probability).
"""

from __future__ import annotations

from hotirjam_ai5.break_capability.break_models import (
    EvidenceAggregatorResult,
    ObjectivePressureResult,
    ResistanceEvaluationResult,
    TargetType,
)
from hotirjam_ai5.continuation import ContinuationSnapshot, ContinuationState
from hotirjam_ai5.initiative import InitiativeSnapshot, InitiativeState
from hotirjam_ai5.response import ResponseSnapshot


def aggregate_break_evidence(
    *,
    pressure: ObjectivePressureResult,
    resistance: ResistanceEvaluationResult,
    initiative: InitiativeSnapshot,
    response: ResponseSnapshot,
    continuation: ContinuationSnapshot,
) -> EvidenceAggregatorResult:
    """Compute break_probability 0–100 from pressure vs resistance and context."""
    if pressure.target_type is TargetType.NONE:
        return EvidenceAggregatorResult(
            0.0,
            ("No target objective — break probability 0",),
        )

    # Core: pressure advantage over resistance.
    # Equal pressure/resistance ≈ 50; pressure 100 resistance 0 ≈ 100.
    spread = pressure.pressure_score - resistance.resistance_score
    core = 50.0 + spread * 0.5
    core = max(0.0, min(100.0, core))

    reasons: list[str] = [
        f"Pressure {pressure.pressure_score:.1f} vs resistance {resistance.resistance_score:.1f}",
        f"Core capability {core:.1f}",
    ]

    adjust = 0.0
    if continuation.state is ContinuationState.STRONG:
        adjust += 8.0
        reasons.append("Strong continuation supports break capability")
    elif continuation.state is ContinuationState.WEAK:
        adjust -= 8.0
        reasons.append("Weak continuation reduces break capability")

    if initiative.state is InitiativeState.DOMINANT:
        adjust += 5.0
        reasons.append("Dominant initiative supports break capability")
    elif initiative.state in {InitiativeState.NONE, InitiativeState.EXPIRED}:
        adjust -= 5.0
        reasons.append("Absent initiative reduces break capability")
    elif initiative.state is InitiativeState.WEAKENING:
        adjust -= 2.0
        reasons.append("Weakening initiative mildly reduces break capability")

    if response.initiative_preserved:
        adjust += 4.0
        reasons.append("Initiative preserved supports break capability")
    else:
        adjust -= 12.0
        reasons.append("Initiative lost — break capability reduced")

    decay_penalty = continuation.momentum_decay * 0.10
    adjust -= decay_penalty
    reasons.append(f"Momentum decay penalty {decay_penalty:.1f}")

    probability = max(0.0, min(100.0, core + adjust))
    reasons.append(f"Break probability {probability:.1f}")
    return EvidenceAggregatorResult(probability, tuple(reasons))
