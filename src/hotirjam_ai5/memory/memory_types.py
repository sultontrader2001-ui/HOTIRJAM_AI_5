"""Market Memory types (Sprint 41) — passive observation history."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MemorySource(StrEnum):
    """Producer stream that contributed a memory record."""

    PHYSICS = "PHYSICS"
    LIQUIDITY = "LIQUIDITY"
    STATE = "STATE"
    BEHAVIOR = "BEHAVIOR"
    DECISION = "DECISION"


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """Immutable memory record derived from an engine snapshot.

    Append-only: never mutate after creation. No raw ticks or raw DOM.
    """

    timestamp: float
    source: MemorySource
    direction: str
    strength: float
    confidence: float

    def __post_init__(self) -> None:
        if self.strength < 0:
            raise ValueError("strength must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
