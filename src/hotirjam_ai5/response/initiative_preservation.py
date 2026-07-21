"""RE03 — Initiative Preservation.

Determines whether the original initiative survived the counter-response.
"""

from __future__ import annotations

from hotirjam_ai5.initiative import InitiativeSide, InitiativeSnapshot
from hotirjam_ai5.response.response_models import (
    CounterMoveResult,
    InitiativePreservationResult,
    ResponseStrengthResult,
)


def evaluate_initiative_preservation(
    *,
    initiative: InitiativeSnapshot,
    counter: CounterMoveResult,
    strength: ResponseStrengthResult,
) -> InitiativePreservationResult:
    """Return whether initiative still holds after the response attempt."""
    if initiative.initiative_side is InitiativeSide.NONE:
        return InitiativePreservationResult(
            True,
            ("No initiative to threaten",),
        )

    if not counter.detected:
        return InitiativePreservationResult(
            True,
            ("No counter move — initiative preserved",),
        )

    # Strong counter relative to initiative → initiative lost.
    # Weak/failed counter → preserved.
    initiative_floor = max(25.0, initiative.initiative_score * 0.55)
    if strength.strength >= 70.0 and strength.strength >= initiative_floor:
        return InitiativePreservationResult(
            False,
            (
                f"Strong counter ({strength.strength:.1f}) overcame initiative "
                f"({initiative.initiative_score:.1f})",
            ),
        )

    if strength.strength >= 50.0 and counter.magnitude_ticks >= 8.0:
        return InitiativePreservationResult(
            False,
            (
                f"Material counter ({counter.magnitude_ticks:.1f} ticks, "
                f"strength {strength.strength:.1f}) challenged initiative",
            ),
        )

    return InitiativePreservationResult(
        True,
        (
            f"Counter strength {strength.strength:.1f} insufficient to erase initiative "
            f"({initiative.initiative_score:.1f})",
        ),
    )
