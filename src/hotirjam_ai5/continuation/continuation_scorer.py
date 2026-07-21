"""CT04 — Continuation Scorer.

Combines pressure, momentum decay, and candle continuation into one snapshot.
No breakout probability. No trade decisions.
"""

from __future__ import annotations

from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.continuation.continuation_models import (
    ContinuationSide,
    ContinuationState,
    ContinuationStrengthResult,
    MomentumDecayResult,
    PressurePersistenceResult,
)
from hotirjam_ai5.continuation.continuation_snapshot import ContinuationSnapshot


def _side_from_initiative(side: InitiativeSide) -> ContinuationSide:
    if side is InitiativeSide.BUYER:
        return ContinuationSide.BUYER
    if side is InitiativeSide.SELLER:
        return ContinuationSide.SELLER
    return ContinuationSide.NONE


def _state_from_score(score: float) -> ContinuationState:
    if score < 35.0:
        return ContinuationState.WEAK
    if score < 70.0:
        return ContinuationState.MEDIUM
    return ContinuationState.STRONG


def score_continuation(
    *,
    initiative: InitiativeSnapshot,
    pressure: PressurePersistenceResult,
    decay: MomentumDecayResult,
    strength: ContinuationStrengthResult,
    objectives: ObjectiveSnapshot,
    timestamp: float,
) -> ContinuationSnapshot:
    """Produce ContinuationSnapshot from CT01–CT03."""
    reasons: list[str] = []
    reasons.extend(pressure.reasons)
    reasons.extend(decay.reasons)
    reasons.extend(strength.reasons)

    # Decay reduces continuation: persistence_factor = 100 - decay.
    persistence = 100.0 - decay.momentum_decay
    continuation_score = (
        0.40 * pressure.pressure_score
        + 0.30 * persistence
        + 0.30 * strength.strength_score
    )
    continuation_score = max(0.0, min(100.0, continuation_score))

    if initiative.initiative_side is InitiativeSide.NONE:
        side = ContinuationSide.NONE
        reasons.append("No initiative — continuation side NONE")
    elif continuation_score < 20.0:
        side = ContinuationSide.NONE
        reasons.append("Continuation too weak — side cleared")
    else:
        side = _side_from_initiative(initiative.initiative_side)
        reasons.append(f"Continuation side {side.value}")

    state = _state_from_score(continuation_score)
    if side is ContinuationSide.NONE:
        state = ContinuationState.WEAK

    # Confidence from agreement: high pressure + low decay + high strength.
    agreement_parts = 0
    if pressure.pressure_score >= 40.0:
        agreement_parts += 1
    if decay.momentum_decay <= 50.0:
        agreement_parts += 1
    if strength.strength_score >= 40.0:
        agreement_parts += 1
    confidence = (agreement_parts / 3.0) * 100.0
    if objectives.is_complete and side is not ContinuationSide.NONE:
        confidence = min(100.0, confidence + 5.0)
        reasons.append("Objectives present — confidence reinforced")

    return ContinuationSnapshot(
        continuation_side=side,
        continuation_score=continuation_score,
        pressure_score=pressure.pressure_score,
        momentum_decay=decay.momentum_decay,
        state=state,
        confidence=confidence,
        reasons=tuple(reasons),
        timestamp=timestamp,
    )
