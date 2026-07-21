"""BK02 — Resistance Evaluation.

Measures how much resistance remains before the active objective.
Higher score = harder to break.
"""

from __future__ import annotations

from hotirjam_ai5.break_capability.break_models import (
    ObjectivePressureResult,
    ResistanceEvaluationResult,
    TargetType,
)
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSnapshot, ResponseState


def evaluate_resistance(
    *,
    objectives: ObjectiveSnapshot,
    pressure: ObjectivePressureResult,
    response: ResponseSnapshot,
) -> ResistanceEvaluationResult:
    """Score remaining resistance ahead of the target objective (0–100)."""
    if pressure.target_type is TargetType.NONE:
        return ResistanceEvaluationResult(0.0, ("No target — resistance not applicable",))

    if pressure.target_type is TargetType.HIGH:
        strength = objectives.nearest_high_strength
        distance = objectives.nearest_high_distance_ticks
    else:
        strength = objectives.nearest_low_strength
        distance = objectives.nearest_low_distance_ticks

    if strength is None or distance is None:
        return ResistanceEvaluationResult(100.0, ("Objective data incomplete — max resistance",))

    # Structural resistance from objective strength (already 0–100).
    structure = max(0.0, min(100.0, strength))

    # Path resistance: farther = more remaining resistance (40 ticks ≈ full).
    path = max(0.0, min(100.0, (distance / 40.0) * 100.0))

    # Opposing response adds resistance.
    if response.response_state is ResponseState.STRONG:
        response_boost = 25.0
        response_note = "Strong response adds resistance"
    elif response.response_state is ResponseState.NEUTRAL:
        response_boost = 10.0
        response_note = "Neutral response adds mild resistance"
    elif response.response_state is ResponseState.WEAK:
        response_boost = 5.0
        response_note = "Weak response adds slight resistance"
    else:
        response_boost = 0.0
        response_note = "Failed response — no added resistance"

    if not response.initiative_preserved:
        response_boost = min(100.0, response_boost + 20.0)
        response_note = response_note + "; initiative lost"

    resistance = 0.50 * structure + 0.35 * path + 0.15 * min(100.0, response_boost * (100.0 / 25.0))
    resistance = max(0.0, min(100.0, resistance))

    reasons = (
        f"Objective strength {structure:.1f}",
        f"Path distance {distance:.1f} ticks (path resistance {path:.1f})",
        response_note,
        f"Resistance score {resistance:.1f}",
    )
    return ResistanceEvaluationResult(resistance, reasons)
