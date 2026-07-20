"""Tests for EventLog."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.event_log import EventLog


def test_append_and_latest_order() -> None:
    log = EventLog(capacity=5)
    log.append("one")
    log.append("two")
    assert log.latest() == ("one", "two")
    assert len(log) == 2


def test_capacity_evicts_oldest() -> None:
    log = EventLog(capacity=2)
    log.append("a")
    log.append("b")
    log.append("c")
    assert log.latest() == ("b", "c")


def test_default_capacity_is_five() -> None:
    log = EventLog()
    for index in range(7):
        log.append(f"event-{index}")
    assert len(log) == 5
    assert log.latest() == (
        "event-2",
        "event-3",
        "event-4",
        "event-5",
        "event-6",
    )


def test_reject_empty_message() -> None:
    log = EventLog()
    with pytest.raises(ValueError, match="non-empty"):
        log.append("   ")


def test_reject_invalid_capacity() -> None:
    with pytest.raises(ValueError, match="capacity"):
        EventLog(capacity=0)


def test_clear() -> None:
    log = EventLog()
    log.append("x")
    log.clear()
    assert log.latest() == ()
    assert len(log) == 0
