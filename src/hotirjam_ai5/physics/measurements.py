"""Immutable physics measurement snapshot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PhysicsSnapshot:
    """Latest physics values derived from live ticks.

    Velocity requires two ticks; acceleration requires two velocity samples.
    Missing values stay ``None`` — never invented.
    """

    spread: float | None = None
    mid_price: float | None = None
    tick_velocity: float | None = None
    tick_acceleration: float | None = None
    tick_count: int = 0
