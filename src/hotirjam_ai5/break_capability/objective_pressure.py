"""BK01 — Objective Pressure.

Measures how much pressure is applied toward the active objective.
"""

from __future__ import annotations

from hotirjam_ai5.break_capability.break_models import (
    ObjectivePressureResult,
    TargetSide,
    TargetType,
)
from hotirjam_ai5.continuation import ContinuationSide, ContinuationSnapshot
from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSnapshot, ResponseState


def _resolve_target(
    initiative: InitiativeSnapshot,
    continuation: ContinuationSnapshot,
) -> tuple[TargetSide, TargetType]:
    """Choose the objective under pressure from initiative / continuation."""
    # Continuation side leads when present; else initiative.
    if continuation.continuation_side is ContinuationSide.BUYER:
        return TargetSide.BUYER, TargetType.HIGH
    if continuation.continuation_side is ContinuationSide.SELLER:
        return TargetSide.SELLER, TargetType.LOW
    if initiative.initiative_side is InitiativeSide.BUYER:
        return TargetSide.BUYER, TargetType.HIGH
    if initiative.initiative_side is InitiativeSide.SELLER:
        return TargetSide.SELLER, TargetType.LOW
    return TargetSide.NONE, TargetType.NONE


def measure_objective_pressure(
    *,
    objectives: ObjectiveSnapshot,
    initiative: InitiativeSnapshot,
    response: ResponseSnapshot,
    continuation: ContinuationSnapshot,
) -> ObjectivePressureResult:
    """Score pressure toward the active objective (0–100)."""
    side, target = _resolve_target(initiative, continuation)
    if side is TargetSide.NONE or target is TargetType.NONE:
        return ObjectivePressureResult(
            0.0,
            TargetSide.NONE,
            TargetType.NONE,
            ("No active side — no objective pressure",),
        )

    if target is TargetType.HIGH and not objectives.has_high:
        return ObjectivePressureResult(
            0.0,
            side,
            TargetType.NONE,
            ("Nearest high unavailable — cannot apply HIGH pressure",),
        )
    if target is TargetType.LOW and not objectives.has_low:
        return ObjectivePressureResult(
            0.0,
            side,
            TargetType.NONE,
            ("Nearest low unavailable — cannot apply LOW pressure",),
        )

    # Proximity: closer to objective → higher pressure contribution.
    if target is TargetType.HIGH:
        distance = objectives.nearest_high_distance_ticks or 0.0
    else:
        distance = objectives.nearest_low_distance_ticks or 0.0
    # 0 ticks → 100; 40+ ticks → ~0
    proximity = max(0.0, min(100.0, 100.0 - (distance / 40.0) * 100.0))

    initiative_part = initiative.initiative_score
    continuation_part = 0.5 * continuation.continuation_score + 0.5 * continuation.pressure_score

    # Response: preserved + failed counter helps pressure; strong counter hurts.
    if not response.initiative_preserved:
        response_factor = 0.40
        response_note = "Initiative not preserved — pressure heavily discounted"
    elif response.response_state is ResponseState.STRONG:
        response_factor = 0.55
        response_note = "Strong opposing response — pressure discounted"
    elif response.response_state is ResponseState.FAILED:
        response_factor = 1.0
        response_note = "Failed response — pressure intact"
    else:
        response_factor = 0.80
        response_note = f"Response {response.response_state.value} — mild discount"

    base = 0.35 * initiative_part + 0.40 * continuation_part + 0.25 * proximity
    pressure = max(0.0, min(100.0, base * response_factor))

    reasons = (
        f"Target {side.value} → {target.value}",
        f"Distance {distance:.1f} ticks (proximity {proximity:.1f})",
        f"Initiative {initiative_part:.1f}, continuation blend {continuation_part:.1f}",
        response_note,
        f"Pressure score {pressure:.1f}",
    )
    return ObjectivePressureResult(pressure, side, target, reasons)
