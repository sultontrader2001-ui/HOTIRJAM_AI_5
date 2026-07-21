"""ContinuationSnapshot — whether initiative pressure is continuing or fading."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.continuation.continuation_models import ContinuationSide, ContinuationState


@dataclass(frozen=True, slots=True)
class ContinuationSnapshot:
    """Continuation evaluation at one moment. Never encodes trade decisions."""

    continuation_side: ContinuationSide
    continuation_score: float
    pressure_score: float
    momentum_decay: float
    state: ContinuationState
    confidence: float
    reasons: tuple[str, ...]
    timestamp: float

    @classmethod
    def empty(
        cls,
        *,
        timestamp: float,
        reason: str = "Insufficient market data",
    ) -> ContinuationSnapshot:
        """Neutral snapshot when inputs are empty or invalid."""
        return cls(
            continuation_side=ContinuationSide.NONE,
            continuation_score=0.0,
            pressure_score=0.0,
            momentum_decay=0.0,
            state=ContinuationState.WEAK,
            confidence=0.0,
            reasons=(reason,),
            timestamp=timestamp,
        )
