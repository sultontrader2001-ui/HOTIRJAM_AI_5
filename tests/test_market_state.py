"""Unit tests for Market State Engine (Sprint 6) — observation only."""

from __future__ import annotations

from hotirjam_ai5.market_state import (
    MarketState,
    MarketStateEngine,
    MarketStateInputs,
)
from hotirjam_ai5.market_state.classifier import classify_market_state


def _inputs(**overrides: object) -> MarketStateInputs:
    base = {
        "tick_count": 100,
        "tick_rate": 3.0,
        "feed_connected": True,
        "feed_stale": False,
        "connection_quality": "GOOD",
        "spread": 0.25,
        "tick_velocity": 0.5,
        "tick_acceleration": 0.1,
        "dom_update_rate": 5.0,
    }
    base.update(overrides)
    return MarketStateInputs(**base)  # type: ignore[arg-type]


def test_unknown_when_no_ticks() -> None:
    state, reason = classify_market_state(_inputs(tick_count=0, tick_rate=0.0))
    assert state is MarketState.UNKNOWN
    assert "Insufficient" in reason


def test_unknown_when_disconnected() -> None:
    state, reason = classify_market_state(_inputs(feed_connected=False))
    assert state is MarketState.UNKNOWN
    assert "Insufficient" in reason


def test_unknown_when_feed_stale() -> None:
    state, reason = classify_market_state(_inputs(feed_stale=True))
    assert state is MarketState.UNKNOWN
    assert "stale" in reason.lower()


def test_quiet_low_tick_activity() -> None:
    state, reason = classify_market_state(
        _inputs(
            tick_rate=0.5,
            tick_velocity=0.1,
            tick_acceleration=0.0,
        )
    )
    assert state is MarketState.QUIET
    assert "Low tick" in reason


def test_normal_steady_activity() -> None:
    state, reason = classify_market_state(
        _inputs(
            tick_rate=3.0,
            tick_velocity=0.5,
            tick_acceleration=0.1,
        )
    )
    assert state is MarketState.NORMAL
    assert "Steady" in reason


def test_active_elevated_tick_rate() -> None:
    state, reason = classify_market_state(
        _inputs(
            tick_rate=8.0,
            tick_velocity=0.8,
            tick_acceleration=0.2,
        )
    )
    assert state is MarketState.ACTIVE
    assert "Tick activity" in reason


def test_trending_sustained_velocity() -> None:
    state, reason = classify_market_state(
        _inputs(
            tick_rate=4.0,
            tick_velocity=2.5,
            tick_acceleration=0.5,
        )
    )
    assert state is MarketState.TRENDING
    assert "velocity" in reason.lower()


def test_trending_stable_across_repeated_calls() -> None:
    inputs = _inputs(tick_rate=4.0, tick_velocity=-3.0, tick_acceleration=0.2)
    first = classify_market_state(inputs)
    second = classify_market_state(inputs)
    assert first == second
    assert first[0] is MarketState.TRENDING


def test_volatile_high_acceleration() -> None:
    state, reason = classify_market_state(
        _inputs(
            tick_rate=6.0,
            tick_velocity=1.0,
            tick_acceleration=4.0,
        )
    )
    assert state is MarketState.VOLATILE
    assert "Rapid" in reason or "Unstable" in reason


def test_volatile_wide_spread_with_velocity() -> None:
    state, reason = classify_market_state(
        _inputs(
            tick_rate=3.0,
            spread=1.5,
            tick_velocity=2.5,
            tick_acceleration=0.5,
        )
    )
    assert state is MarketState.VOLATILE
    assert "spread" in reason.lower() or "Unstable" in reason


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([100.0, 101.0, 102.0]).__next__
    engine = MarketStateEngine(clock=clock)
    snap = engine.evaluate(
        _inputs(tick_rate=8.0, tick_velocity=0.5, tick_acceleration=0.1)
    )
    assert snap.state is MarketState.ACTIVE
    assert snap.timestamp == 101.0  # 100.0 consumed by __init__
    assert engine.snapshot() is snap


def test_engine_starts_unknown() -> None:
    engine = MarketStateEngine(clock=lambda: 1.0)
    assert engine.snapshot().state is MarketState.UNKNOWN


def test_classification_never_emits_trading_words() -> None:
    cases = [
        _inputs(tick_count=0),
        _inputs(tick_rate=0.2),
        _inputs(tick_rate=3.0),
        _inputs(tick_rate=10.0),
        _inputs(tick_velocity=3.0, tick_acceleration=0.1),
        _inputs(tick_acceleration=5.0),
    ]
    banned = ("BUY", "SELL", "LONG", "SHORT", "entry", "exit", "risk", "confidence")
    for inputs in cases:
        _, reason = classify_market_state(inputs)
        lowered = reason.lower()
        for word in banned:
            assert word.lower() not in lowered
