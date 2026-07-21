"""RE04 — Response Scorer.

Combines counter-move, strength, and preservation into ResponseSnapshot.
No breakout, continuation, or trade decisions.
"""

from __future__ import annotations

from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response.response_models import (
    CounterMoveResult,
    InitiativePreservationResult,
    ResponseSide,
    ResponseState,
    ResponseStrengthResult,
)
from hotirjam_ai5.response.response_snapshot import ResponseSnapshot


def _state_from_strength(
    *,
    counter: CounterMoveResult,
    strength: float,
) -> ResponseState:
    if not counter.detected or strength < 15.0:
        return ResponseState.FAILED
    if strength < 35.0:
        return ResponseState.WEAK
    if strength < 65.0:
        return ResponseState.NEUTRAL
    return ResponseState.STRONG


def score_response(
    *,
    counter: CounterMoveResult,
    strength: ResponseStrengthResult,
    preservation: InitiativePreservationResult,
    objectives: ObjectiveSnapshot,
    timestamp: float,
) -> ResponseSnapshot:
    """Produce the final ResponseSnapshot."""
    reasons: list[str] = []
    reasons.extend(counter.reasons)
    reasons.extend(strength.reasons)
    reasons.extend(preservation.reasons)

    state = _state_from_strength(counter=counter, strength=strength.strength)
    side = counter.response_side if counter.detected else ResponseSide.NONE

    # Confidence: clearer detection + stronger signal → higher.
    if not counter.detected:
        confidence = 20.0 if "No initiative" in " ".join(counter.reasons) else 40.0
    else:
        confidence = min(100.0, 40.0 + strength.strength * 0.5)
        if objectives.is_complete:
            confidence = min(100.0, confidence + 5.0)
            reasons.append("Objectives present — confidence reinforced")

    return ResponseSnapshot(
        response_side=side,
        response_strength=strength.strength,
        response_state=state,
        initiative_preserved=preservation.preserved,
        confidence=confidence,
        reasons=tuple(reasons),
        timestamp=timestamp,
    )
