"""Tests for tick velocity tracker."""

from __future__ import annotations

import pytest

from hotirjam_ai5.physics.tick_velocity import TickVelocityTracker


def test_first_update_returns_none() -> None:
    tracker = TickVelocityTracker()
    assert tracker.update(price=100.0, timestamp=1.0) is None


def test_velocity_is_price_change_over_time() -> None:
    tracker = TickVelocityTracker()
    assert tracker.update(price=100.0, timestamp=10.0) is None
    sample = tracker.update(price=102.0, timestamp=12.0)
    assert sample is not None
    assert sample.price_change == 2.0
    assert sample.time_seconds == 2.0
    assert sample.velocity == pytest.approx(1.0)
    assert sample.timestamp == 12.0


def test_non_positive_delta_t_returns_none_but_advances_state() -> None:
    tracker = TickVelocityTracker()
    tracker.update(price=100.0, timestamp=10.0)
    assert tracker.update(price=101.0, timestamp=10.0) is None
    sample = tracker.update(price=103.0, timestamp=11.0)
    assert sample is not None
    assert sample.velocity == pytest.approx(2.0)


def test_reset_clears_state() -> None:
    tracker = TickVelocityTracker()
    tracker.update(price=1.0, timestamp=1.0)
    tracker.update(price=2.0, timestamp=2.0)
    tracker.reset()
    assert tracker.update(price=3.0, timestamp=3.0) is None
