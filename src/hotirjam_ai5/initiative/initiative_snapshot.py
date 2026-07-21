"""InitiativeSnapshot — present auction-control observation (H-5)."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.initiative.initiative_models import (
    InitiativeEvidence,
    InitiativeSide,
    InitiativeState,
)


@dataclass(frozen=True, slots=True)
class InitiativeSnapshot:
    """Initiative at one moment. Never encodes trade decisions."""

    buyer_initiative: float
    seller_initiative: float
    dominant_side: InitiativeSide
    initiative_state: InitiativeState
    confidence: float
    evidence: InitiativeEvidence
    reasons: tuple[str, ...]
    timestamp: float

    @classmethod
    def empty(
        cls,
        *,
        timestamp: float,
        reason: str = "Insufficient market data",
        state: InitiativeState = InitiativeState.NONE,
    ) -> InitiativeSnapshot:
        """Neutral snapshot when inputs cannot support an observation."""
        return cls(
            buyer_initiative=0.0,
            seller_initiative=0.0,
            dominant_side=InitiativeSide.NONE,
            initiative_state=state,
            confidence=0.0,
            evidence=InitiativeEvidence(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            reasons=(reason,),
            timestamp=timestamp,
        )

    # ------------------------------------------------------------------ compat
    # Downstream observation engines still read these accessors. They map onto
    # H-5 fields and never reintroduce trade vocabulary.

    @property
    def initiative_side(self) -> InitiativeSide:
        return self.dominant_side

    @property
    def initiative_score(self) -> float:
        if self.dominant_side is InitiativeSide.BUYER:
            return self.buyer_initiative
        if self.dominant_side is InitiativeSide.SELLER:
            return self.seller_initiative
        return max(self.buyer_initiative, self.seller_initiative)

    @property
    def state(self) -> InitiativeState:
        return self.initiative_state

    @property
    def impulse_score(self) -> float:
        return self.evidence.force

    @property
    def momentum_score(self) -> float:
        return self.evidence.motion

    @property
    def candle_strength_score(self) -> float:
        return self.evidence.pressure
