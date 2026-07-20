"""Market transition observation models (Sprint 7)."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.market_state import MarketState


NO_TRANSITION = "NONE"


@dataclass(frozen=True, slots=True)
class TransitionSnapshot:
    """A reported market-state transition that has already occurred."""

    current_state: MarketState
    previous_state: MarketState | None
    transition: str
    changed: bool
    duration_seconds: float
    reason: str
    timestamp: float
