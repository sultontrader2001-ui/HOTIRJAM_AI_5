"""ResponseSnapshot — opposing-side reaction after initiative."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.response.response_models import ResponseSide, ResponseState


@dataclass(frozen=True, slots=True)
class ResponseSnapshot:
    """Counter-response evaluation at one moment. Never encodes trade decisions."""

    response_side: ResponseSide
    response_strength: float
    response_state: ResponseState
    initiative_preserved: bool
    confidence: float
    reasons: tuple[str, ...]
    timestamp: float

    @classmethod
    def empty(
        cls,
        *,
        timestamp: float,
        reason: str = "Insufficient market data",
        initiative_preserved: bool = True,
    ) -> ResponseSnapshot:
        """Neutral snapshot when inputs are empty or invalid."""
        return cls(
            response_side=ResponseSide.NONE,
            response_strength=0.0,
            response_state=ResponseState.NEUTRAL,
            initiative_preserved=initiative_preserved,
            confidence=0.0,
            reasons=(reason,),
            timestamp=timestamp,
        )
