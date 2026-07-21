"""ObjectiveSnapshot — nearest eligible structural objectives at one moment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObjectivePersistenceState(StrEnum):
    """Per-side Objective Engine persistence transition."""

    NEW = "NEW"
    PERSISTED = "PERSISTED"
    REPLACED = "REPLACED"
    BREACHED = "BREACHED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class ObjectiveSnapshot:
    """Nearest eligible structural Swing High and Swing Low relative to price.

    Observation only. Never encodes trade direction or decisions.
    Missing objectives use ``None`` (empty / invalid / insufficient swings).
    """

    nearest_high_price: float | None
    nearest_high_distance_ticks: float | None
    nearest_high_strength: float | None
    nearest_low_price: float | None
    nearest_low_distance_ticks: float | None
    nearest_low_strength: float | None
    current_price: float | None
    timestamp: float
    high_state: ObjectivePersistenceState | None = None
    low_state: ObjectivePersistenceState | None = None

    @classmethod
    def empty(cls, *, timestamp: float, current_price: float | None = None) -> ObjectiveSnapshot:
        """Snapshot with no identifiable objectives."""
        return cls(
            nearest_high_price=None,
            nearest_high_distance_ticks=None,
            nearest_high_strength=None,
            nearest_low_price=None,
            nearest_low_distance_ticks=None,
            nearest_low_strength=None,
            current_price=current_price,
            timestamp=timestamp,
            high_state=None,
            low_state=None,
        )

    @property
    def has_high(self) -> bool:
        return self.nearest_high_price is not None

    @property
    def has_low(self) -> bool:
        return self.nearest_low_price is not None

    @property
    def is_complete(self) -> bool:
        """True when both nearest high and nearest low are present."""
        return self.has_high and self.has_low
