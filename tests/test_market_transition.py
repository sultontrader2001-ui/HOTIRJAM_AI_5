"""Unit tests for Market Transition Engine (Sprint 7)."""

from __future__ import annotations

import pytest

from hotirjam_ai5.market_state import MarketState, MarketStateSnapshot
from hotirjam_ai5.market_transition import MarketTransitionEngine, NO_TRANSITION


def _state(state: MarketState, timestamp: float) -> MarketStateSnapshot:
    return MarketStateSnapshot(
        state=state,
        reason="Observed market condition",
        timestamp=timestamp,
    )


def test_first_snapshot_has_no_transition() -> None:
    engine = MarketTransitionEngine()
    result = engine.evaluate(_state(MarketState.QUIET, 100.0), None)

    assert result.current_state is MarketState.QUIET
    assert result.previous_state is None
    assert result.transition == NO_TRANSITION
    assert result.changed is False
    assert result.duration_seconds == 0.0
    assert result.timestamp == 100.0


def test_no_change_reports_none() -> None:
    engine = MarketTransitionEngine()
    previous = _state(MarketState.ACTIVE, 100.0)
    engine.evaluate(previous, None)

    result = engine.evaluate(_state(MarketState.ACTIVE, 106.0), previous)

    assert result.previous_state is MarketState.ACTIVE
    assert result.current_state is MarketState.ACTIVE
    assert result.transition == NO_TRANSITION
    assert result.changed is False
    assert result.duration_seconds == pytest.approx(6.0)


def test_state_change_reports_completed_transition() -> None:
    engine = MarketTransitionEngine()
    previous = _state(MarketState.ACTIVE, 100.0)
    engine.evaluate(previous, None)

    result = engine.evaluate(_state(MarketState.TRENDING, 118.0), previous)

    assert result.previous_state is MarketState.ACTIVE
    assert result.current_state is MarketState.TRENDING
    assert result.transition == "ACTIVE → TRENDING"
    assert result.changed is True
    assert result.duration_seconds == pytest.approx(18.0)
    assert "changed" in result.reason


def test_repeated_updates_track_duration_since_state_started() -> None:
    engine = MarketTransitionEngine()
    first = _state(MarketState.NORMAL, 10.0)
    second = _state(MarketState.NORMAL, 14.0)
    third = _state(MarketState.NORMAL, 21.5)

    engine.evaluate(first, None)
    engine.evaluate(second, first)
    result = engine.evaluate(third, second)

    assert result.transition == NO_TRANSITION
    assert result.changed is False
    assert result.duration_seconds == pytest.approx(11.5)
    assert engine.snapshot() is result


def test_duration_resets_after_state_change() -> None:
    engine = MarketTransitionEngine()
    quiet = _state(MarketState.QUIET, 10.0)
    active = _state(MarketState.ACTIVE, 20.0)
    active_later = _state(MarketState.ACTIVE, 25.0)

    engine.evaluate(quiet, None)
    changed = engine.evaluate(active, quiet)
    unchanged = engine.evaluate(active_later, active)

    assert changed.duration_seconds == pytest.approx(10.0)
    assert unchanged.duration_seconds == pytest.approx(5.0)


def test_negative_timestamp_difference_is_clamped_to_zero() -> None:
    engine = MarketTransitionEngine()
    previous = _state(MarketState.VOLATILE, 20.0)
    engine.evaluate(previous, None)

    result = engine.evaluate(_state(MarketState.NORMAL, 19.0), previous)

    assert result.changed is True
    assert result.duration_seconds == 0.0


def test_transition_output_never_predicts_or_advises() -> None:
    engine = MarketTransitionEngine()
    previous = _state(MarketState.TRENDING, 1.0)
    engine.evaluate(previous, None)
    result = engine.evaluate(_state(MarketState.VOLATILE, 2.0), previous)

    output = f"{result.transition} {result.reason}".lower()
    for banned in ("buy", "sell", "forecast", "confidence"):
        assert banned not in output
