"""InitiativeSnapshot — current market initiative observation."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.initiative.initiative_models import InitiativeSide, InitiativeState


@dataclass(frozen=True, slots=True)
class InitiativeSnapshot:
    """Initiative evaluation at one moment. Never encodes trade decisions."""

    initiative_side: InitiativeSide
    impulse_score: float
    momentum_score: float
    candle_strength_score: float
    initiative_score: float
    state: InitiativeState
    confidence: float
    reasons: tuple[str, ...]
    timestamp: float

    @classmethod
    def empty(cls, *, timestamp: float, reason: str = "Insufficient market data") -> InitiativeSnapshot:
        """Neutral snapshot when inputs are empty or invalid."""
        return cls(
            initiative_side=InitiativeSide.NONE,
            impulse_score=0.0,
            momentum_score=0.0,
            candle_strength_score=0.0,
            initiative_score=0.0,
            state=InitiativeState.WEAK,
            confidence=0.0,
            reasons=(reason,),
            timestamp=timestamp,
        )
