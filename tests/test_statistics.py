"""Tests for SessionStatistics."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.statistics import SessionStatistics


class FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_initial_counters_are_zero() -> None:
    stats = SessionStatistics(clock=FakeClock())
    assert stats.tick_count == 0
    assert stats.tick_rate() == 0.0
    assert stats.running_time_seconds() == 0.0


def test_tick_rate_over_elapsed_time() -> None:
    clock = FakeClock(0.0)
    stats = SessionStatistics(clock=clock)
    stats.record_tick(10)
    clock.now = 5.0
    assert stats.running_time_seconds() == 5.0
    assert stats.tick_rate() == 2.0


def test_record_tick_rejects_non_positive() -> None:
    stats = SessionStatistics(clock=FakeClock())
    with pytest.raises(ValueError, match="at least 1"):
        stats.record_tick(0)


def test_reset_clears_and_restarts_clock() -> None:
    clock = FakeClock(10.0)
    stats = SessionStatistics(clock=clock)
    stats.record_tick(3)
    clock.now = 20.0
    stats.reset()
    assert stats.tick_count == 0
    assert stats.running_time_seconds() == 0.0
    clock.now = 25.0
    assert stats.running_time_seconds() == 5.0
