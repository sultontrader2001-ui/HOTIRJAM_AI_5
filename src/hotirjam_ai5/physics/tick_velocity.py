"""Tick velocity: Δlast_price / Δtimestamp."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VelocitySample:
    """One computed velocity sample."""

    velocity: float
    price_change: float
    time_seconds: float
    timestamp: float


class TickVelocityTracker:
    """Tracks consecutive last prices to compute velocity."""

    def __init__(self) -> None:
        self._previous_price: float | None = None
        self._previous_timestamp: float | None = None

    def update(self, *, price: float, timestamp: float) -> VelocitySample | None:
        """Return velocity when two timestamps with positive Δt are available."""
        if self._previous_price is None or self._previous_timestamp is None:
            self._previous_price = price
            self._previous_timestamp = timestamp
            return None

        time_seconds = timestamp - self._previous_timestamp
        previous_price = self._previous_price
        self._previous_price = price
        self._previous_timestamp = timestamp

        if time_seconds <= 0.0:
            return None

        price_change = price - previous_price
        return VelocitySample(
            velocity=price_change / time_seconds,
            price_change=price_change,
            time_seconds=time_seconds,
            timestamp=timestamp,
        )

    def reset(self) -> None:
        self._previous_price = None
        self._previous_timestamp = None
