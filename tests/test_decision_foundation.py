"""Unit tests for Decision Foundation Engine (Sprint 10)."""

from __future__ import annotations

from hotirjam_ai5.decision_foundation import (
    DecisionFoundationEngine,
    evaluate_decision_foundation,
)
from hotirjam_ai5.decision_foundation.engine import (
    FEED_UNAVAILABLE,
    MISSING_OBSERVATION,
    READY_SUMMARY,
    WAITING_CONTEXT,
)
from hotirjam_ai5.market_context import MarketContextSnapshot


def _context(**overrides: object) -> MarketContextSnapshot:
    base = {
        "timestamp": 100.0,
        "state": "ACTIVE",
        "state_reason": "Tick activity increasing",
        "transition": "NONE",
        "transition_changed": False,
        "transition_duration": 12.0,
        "behavior": "BALANCED",
        "behavior_reason": "Active but balanced",
        "feed_status": "HEALTHY",
        "feed_quality": "GOOD",
        "dom_status": "HEALTHY",
        "dom_quality": "GOOD",
        "tick_rate": 6.0,
        "spread": 0.25,
        "summary": "Active market with balanced behavior.",
    }
    base.update(overrides)
    return MarketContextSnapshot(**base)  # type: ignore[arg-type]


def test_ready_when_observation_layer_complete() -> None:
    snap = evaluate_decision_foundation(_context(), timestamp=200.0)
    assert snap.ready is True
    assert snap.blocking_reason == ""
    assert snap.required_data_complete is True
    assert snap.context_valid is True
    assert snap.observation_complete is True
    assert snap.summary == READY_SUMMARY
    assert snap.timestamp == 200.0


def test_not_ready_when_context_missing() -> None:
    snap = evaluate_decision_foundation(None, timestamp=1.0)
    assert snap.ready is False
    assert snap.blocking_reason == WAITING_CONTEXT
    assert snap.required_data_complete is False
    assert snap.context_valid is False
    assert snap.observation_complete is False
    assert snap.summary == WAITING_CONTEXT


def test_not_ready_when_feed_unavailable() -> None:
    snap = evaluate_decision_foundation(
        _context(feed_status="DISCONNECTED"),
        timestamp=2.0,
    )
    assert snap.ready is False
    assert snap.blocking_reason == FEED_UNAVAILABLE
    assert snap.summary == FEED_UNAVAILABLE


def test_not_ready_when_feed_stale() -> None:
    snap = evaluate_decision_foundation(_context(feed_status="STALE"), timestamp=3.0)
    assert snap.ready is False
    assert snap.blocking_reason == FEED_UNAVAILABLE


def test_not_ready_when_waiting_for_context() -> None:
    snap = evaluate_decision_foundation(
        _context(
            state="UNKNOWN",
            behavior="UNKNOWN",
            summary="Insufficient market context.",
        ),
        timestamp=4.0,
    )
    assert snap.ready is False
    assert snap.blocking_reason == WAITING_CONTEXT
    assert snap.context_valid is False
    assert snap.observation_complete is False


def test_not_ready_when_missing_observation_data() -> None:
    snap = evaluate_decision_foundation(
        _context(state="", behavior="", summary=""),
        timestamp=5.0,
    )
    assert snap.ready is False
    assert snap.blocking_reason == MISSING_OBSERVATION
    assert snap.required_data_complete is False


def test_invalid_context_behavior_unknown() -> None:
    snap = evaluate_decision_foundation(
        _context(behavior="UNKNOWN", summary="Active market with unknown behavior."),
        timestamp=6.0,
    )
    assert snap.ready is False
    assert snap.context_valid is False
    assert snap.blocking_reason == MISSING_OBSERVATION


def test_summary_generation_ready_and_blocked() -> None:
    ready = evaluate_decision_foundation(_context(), timestamp=7.0)
    blocked = evaluate_decision_foundation(None, timestamp=8.0)
    assert ready.summary == "Observation layer complete."
    assert blocked.summary == "Waiting for market context."


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = DecisionFoundationEngine(clock=clock)
    snap = engine.evaluate(_context())
    assert snap.ready is True
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap


def test_output_never_contains_trading_words() -> None:
    cases = [
        None,
        _context(),
        _context(feed_status="DISCONNECTED"),
        _context(state="UNKNOWN", behavior="UNKNOWN", summary="Insufficient market context."),
        _context(state="", behavior="", summary=""),
    ]
    banned = (
        "buy",
        "sell",
        "long",
        "short",
        "entry",
        "exit",
        "signal",
        "confidence",
        "probability",
        "risk",
    )
    for context in cases:
        snap = evaluate_decision_foundation(context, timestamp=1.0)
        text = f"{snap.summary} {snap.blocking_reason}".lower()
        for word in banned:
            assert word not in text
