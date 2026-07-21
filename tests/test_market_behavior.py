"""Unit tests for Market Behavior Engine (Sprint 8) — observation only."""

from __future__ import annotations

from hotirjam_ai5.market_behavior import (
    BehaviorInputs,
    MarketBehavior,
    MarketBehaviorEngine,
    classify_behavior,
)
from hotirjam_ai5.market_state import MarketState


def _inputs(**overrides: object) -> BehaviorInputs:
    base = {
        "market_state": MarketState.NORMAL,
        "transition_changed": False,
        "previous_state": MarketState.NORMAL,
        "tick_count": 100,
        "tick_rate": 3.0,
        "feed_connected": True,
        "feed_stale": False,
        "spread": 0.25,
        "tick_velocity": 0.4,
        "tick_acceleration": 0.0,
        "dom_update_rate": 5.0,
    }
    base.update(overrides)
    return BehaviorInputs(**base)  # type: ignore[arg-type]


def test_unknown_insufficient_information() -> None:
    behavior, reason = classify_behavior(_inputs(tick_count=0))
    assert behavior is MarketBehavior.UNKNOWN
    assert "Insufficient" in reason


def test_unknown_when_market_state_unknown() -> None:
    behavior, reason = classify_behavior(_inputs(market_state=MarketState.UNKNOWN))
    assert behavior is MarketBehavior.UNKNOWN
    assert "Insufficient" in reason


def test_stable_steady_activity() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.QUIET,
            tick_rate=0.5,
            tick_velocity=0.1,
            tick_acceleration=0.0,
        )
    )
    assert behavior is MarketBehavior.STABLE
    assert "steady" in reason.lower()


def test_accelerating_positive_acceleration() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.ACTIVE,
            tick_rate=6.0,
            tick_acceleration=1.2,
        )
    )
    assert behavior is MarketBehavior.ACCELERATING
    assert "increasing" in reason.lower()


def test_accelerating_quiet_to_active_transition() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.ACTIVE,
            previous_state=MarketState.QUIET,
            transition_changed=True,
            tick_rate=6.0,
            tick_acceleration=0.0,
        )
    )
    assert behavior is MarketBehavior.ACCELERATING
    assert "increasing" in reason.lower()


def test_decelerating_negative_acceleration() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.NORMAL,
            tick_acceleration=-1.5,
        )
    )
    assert behavior is MarketBehavior.DECELERATING
    assert "slow" in reason.lower()


def test_decelerating_active_to_quiet_transition() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.QUIET,
            previous_state=MarketState.ACTIVE,
            transition_changed=True,
            tick_rate=0.4,
            tick_acceleration=0.0,
        )
    )
    assert behavior is MarketBehavior.DECELERATING
    assert "slow" in reason.lower()


def test_balanced_active_with_low_acceleration() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.ACTIVE,
            tick_rate=6.0,
            tick_velocity=0.8,
            tick_acceleration=0.1,
        )
    )
    assert behavior is MarketBehavior.BALANCED
    assert "balanced" in reason.lower()


def test_unstable_volatile_state() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.VOLATILE,
            tick_acceleration=0.2,
        )
    )
    assert behavior is MarketBehavior.UNSTABLE
    assert "Volatile" in reason or "inconsistent" in reason.lower()


def test_unstable_high_acceleration() -> None:
    behavior, reason = classify_behavior(
        _inputs(
            market_state=MarketState.TRENDING,
            tick_acceleration=4.5,
        )
    )
    assert behavior is MarketBehavior.UNSTABLE
    assert "Rapid" in reason or "inconsistent" in reason.lower()


def test_classification_stable_across_repeated_calls() -> None:
    inputs = _inputs(market_state=MarketState.QUIET, tick_rate=0.3)
    assert classify_behavior(inputs) == classify_behavior(inputs)


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = MarketBehaviorEngine(clock=clock)
    snap = engine.evaluate(
        _inputs(market_state=MarketState.ACTIVE, tick_rate=6.0, tick_acceleration=0.1)
    )
    assert snap.behavior is MarketBehavior.BALANCED
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap


def test_behavior_never_emits_trading_words() -> None:
    cases = [
        _inputs(tick_count=0),
        _inputs(market_state=MarketState.QUIET, tick_rate=0.2),
        _inputs(tick_acceleration=1.0),
        _inputs(tick_acceleration=-1.0),
        _inputs(market_state=MarketState.ACTIVE, tick_rate=6.0),
        _inputs(market_state=MarketState.VOLATILE),
    ]
    banned = ("BUY", "SELL", "LONG", "SHORT", "entry", "exit", "risk", "confidence")
    for inputs in cases:
        _, reason = classify_behavior(inputs)
        lowered = reason.lower()
        for word in banned:
            assert word.lower() not in lowered
