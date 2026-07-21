"""ObjectiveSnapshot — nearest confirmed objectives at one moment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObjectiveSnapshot:
    """Nearest confirmed Swing High and Swing Low relative to price.

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
