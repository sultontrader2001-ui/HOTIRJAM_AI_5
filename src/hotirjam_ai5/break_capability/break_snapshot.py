"""BreakCapabilitySnapshot — sufficiency to break the active objective."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.break_capability.break_models import (
    BreakCapabilityState,
    TargetSide,
    TargetType,
)


@dataclass(frozen=True, slots=True)
class BreakCapabilitySnapshot:
    """Break capability at one moment. Never encodes trade decisions."""

    target_side: TargetSide
    target_type: TargetType
    break_probability: float
    pressure_score: float
    resistance_score: float
    state: BreakCapabilityState
    confidence: float
    reasons: tuple[str, ...]
    timestamp: float

    @classmethod
    def empty(
        cls,
        *,
        timestamp: float,
        reason: str = "Insufficient market state",
    ) -> BreakCapabilitySnapshot:
        """Neutral snapshot when inputs cannot support a break evaluation."""
        return cls(
            target_side=TargetSide.NONE,
            target_type=TargetType.NONE,
            break_probability=0.0,
            pressure_score=0.0,
            resistance_score=0.0,
            state=BreakCapabilityState.LOW,
            confidence=0.0,
            reasons=(reason,),
            timestamp=timestamp,
        )
