"""Tests for tick acceleration tracker."""

from __future__ import annotations

import pytest

from hotirjam_ai5.physics.tick_acceleration import (
    TickAccelerationTracker,
    compute_tick_acceleration,
)
from hotirjam_ai5.physics.tick_velocity import VelocitySample


def _velocity(velocity: float, timestamp: float) -> VelocitySample:
    return VelocitySample(
        velocity=velocity,
        price_change=velocity,
        time_seconds=1.0,
        timestamp=timestamp,
    )


def test_compute_acceleration() -> None:
    previous = _velocity(1.0, 10.0)
    current = _velocity(3.0, 12.0)
    sample = compute_tick_acceleration(current, previous)
    assert sample.velocity_change == 2.0
    assert sample.time_seconds == 2.0
    assert sample.acceleration == pytest.approx(1.0)


def test_compute_acceleration_rejects_non_positive_dt() -> None:
    with pytest.raises(ValueError, match="timestamp"):
        compute_tick_acceleration(_velocity(1.0, 10.0), _velocity(2.0, 10.0))


def test_tracker_needs_two_samples() -> None:
    tracker = TickAccelerationTracker()
    assert tracker.update(_velocity(1.0, 1.0)) is None
    sample = tracker.update(_velocity(3.0, 2.0))
    assert sample is not None
    assert sample.acceleration == pytest.approx(2.0)


def test_tracker_handles_non_increasing_timestamp() -> None:
    tracker = TickAccelerationTracker()
    tracker.update(_velocity(1.0, 5.0))
    assert tracker.update(_velocity(2.0, 5.0)) is None
    sample = tracker.update(_velocity(4.0, 6.0))
    assert sample is not None
    assert sample.acceleration == pytest.approx(2.0)
