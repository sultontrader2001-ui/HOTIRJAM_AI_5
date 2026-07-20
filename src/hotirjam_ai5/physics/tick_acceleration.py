"""Tick acceleration: Δvelocity / Δtimestamp."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.physics.tick_velocity import VelocitySample


@dataclass(frozen=True, slots=True)
class AccelerationSample:
    """One computed acceleration sample."""

    acceleration: float
    velocity_change: float
    time_seconds: float
    timestamp: float


def compute_tick_acceleration(
    current: VelocitySample,
    previous: VelocitySample,
) -> AccelerationSample:
    """Compute acceleration from two consecutive velocity samples."""
    time_seconds = current.timestamp - previous.timestamp
    if time_seconds <= 0.0:
        raise ValueError("current velocity timestamp must be after previous")
    velocity_change = current.velocity - previous.velocity
    return AccelerationSample(
        acceleration=velocity_change / time_seconds,
        velocity_change=velocity_change,
        time_seconds=time_seconds,
        timestamp=current.timestamp,
    )


class TickAccelerationTracker:
    """Tracks consecutive velocity samples to compute acceleration."""

    def __init__(self) -> None:
        self._previous: VelocitySample | None = None

    def update(self, sample: VelocitySample) -> AccelerationSample | None:
        """Return acceleration when two velocity samples are available."""
        if self._previous is None:
            self._previous = sample
            return None
        try:
            result = compute_tick_acceleration(sample, self._previous)
        except ValueError:
            self._previous = sample
            return None
        self._previous = sample
        return result

    def reset(self) -> None:
        self._previous = None
