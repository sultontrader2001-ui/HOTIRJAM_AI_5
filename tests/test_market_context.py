"""Unit tests for Market Context Engine (Sprint 9) — aggregator only."""

from __future__ import annotations

from hotirjam_ai5.dashboard.dom_health import DomHealthSnapshot
from hotirjam_ai5.dashboard.feed_health import FeedHealthSnapshot
from hotirjam_ai5.dashboard.models import ConnectionQuality, FeedStatus
from hotirjam_ai5.market_behavior.models import BehaviorSnapshot, MarketBehavior
from hotirjam_ai5.market_context import (
    MarketContextEngine,
    MarketContextSnapshot,
    StatisticsSnapshot,
    build_summary,
)
from hotirjam_ai5.market_state import MarketState, MarketStateSnapshot
from hotirjam_ai5.market_transition.models import NO_TRANSITION, TransitionSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot


def _state(
    state: MarketState = MarketState.ACTIVE,
    *,
    reason: str = "Tick activity increasing",
    timestamp: float = 100.0,
) -> MarketStateSnapshot:
    return MarketStateSnapshot(state=state, reason=reason, timestamp=timestamp)


def _transition(
    *,
    current: MarketState = MarketState.ACTIVE,
    previous: MarketState | None = MarketState.QUIET,
    changed: bool = False,
    duration: float = 12.0,
    timestamp: float = 100.0,
) -> TransitionSnapshot:
    return TransitionSnapshot(
        current_state=current,
        previous_state=previous,
        transition=(
            f"{previous.value} → {current.value}"
            if changed and previous is not None
            else NO_TRANSITION
        ),
        changed=changed,
        duration_seconds=duration,
        reason="Observed transition",
        timestamp=timestamp,
    )


def _behavior(
    behavior: MarketBehavior = MarketBehavior.BALANCED,
    *,
    reason: str = "Active but balanced",
    timestamp: float = 100.0,
) -> BehaviorSnapshot:
    return BehaviorSnapshot(behavior=behavior, reason=reason, timestamp=timestamp)


def _feed(
    status: FeedStatus = FeedStatus.HEALTHY,
    quality: ConnectionQuality = ConnectionQuality.GOOD,
) -> FeedHealthSnapshot:
    return FeedHealthSnapshot(
        feed_status=status,
        connection_quality=quality,
        last_tick_age_ms=10.0,
        tick_delay_ms=20.0,
        average_tick_rate=5.0,
        peak_tick_rate=12.0,
    )


def _dom(
    status: FeedStatus = FeedStatus.HEALTHY,
    quality: ConnectionQuality = ConnectionQuality.GOOD,
) -> DomHealthSnapshot:
    return DomHealthSnapshot(
        feed_status=status,
        connection_quality=quality,
        last_update_age_ms=8.0,
        update_rate=10.0,
        peak_update_rate=20.0,
    )


def _physics(*, spread: float | None = 0.25) -> PhysicsSnapshot:
    return PhysicsSnapshot(
        spread=spread,
        mid_price=20100.0,
        tick_velocity=1.0,
        tick_acceleration=0.1,
        tick_count=50,
    )


def _stats(*, tick_rate: float = 4.5) -> StatisticsSnapshot:
    return StatisticsSnapshot(
        tick_count=90,
        tick_rate=tick_rate,
        running_time_seconds=20.0,
    )


def test_context_creation_aggregates_existing_snapshots() -> None:
    engine = MarketContextEngine(clock=lambda: 200.0)
    snap = engine.evaluate(
        market_state=_state(MarketState.TRENDING),
        transition=_transition(current=MarketState.TRENDING, previous=MarketState.ACTIVE),
        behavior=_behavior(MarketBehavior.ACCELERATING, reason="Tick velocity increasing"),
        feed_health=_feed(),
        dom_health=_dom(),
        physics=_physics(spread=0.5),
        statistics=_stats(tick_rate=7.0),
    )

    assert isinstance(snap, MarketContextSnapshot)
    assert snap.timestamp == 200.0
    assert snap.state == "TRENDING"
    assert snap.state_reason == "Tick activity increasing"
    assert snap.transition == "NONE"
    assert snap.transition_changed is False
    assert snap.transition_duration == 12.0
    assert snap.behavior == "ACCELERATING"
    assert snap.behavior_reason == "Tick velocity increasing"
    assert snap.feed_status == "HEALTHY"
    assert snap.feed_quality == "GOOD"
    assert snap.dom_status == "HEALTHY"
    assert snap.dom_quality == "GOOD"
    assert snap.tick_rate == 7.0
    assert snap.spread == 0.5
    assert snap.summary == "Trending market with accelerating behavior."


def test_snapshot_integrity_is_immutable() -> None:
    engine = MarketContextEngine(clock=lambda: 1.0)
    snap = engine.evaluate(
        market_state=_state(),
        transition=_transition(),
        behavior=_behavior(),
        feed_health=_feed(),
        dom_health=_dom(),
        physics=_physics(),
        statistics=_stats(),
    )
    assert engine.snapshot() is snap
    try:
        snap.state = "QUIET"  # type: ignore[misc]
        raised = False
    except Exception:
        raised = True
    assert raised


def test_summary_generation_examples() -> None:
    assert (
        build_summary(
            state=MarketState.VOLATILE,
            behavior=MarketBehavior.UNSTABLE,
            transition_changed=False,
        )
        == "Volatile market with unstable behavior."
    )
    assert (
        build_summary(
            state=MarketState.ACTIVE,
            behavior=MarketBehavior.STABLE,
            transition_changed=False,
        )
        == "Stable active market."
    )
    assert (
        build_summary(
            state=MarketState.QUIET,
            behavior=MarketBehavior.STABLE,
            transition_changed=False,
        )
        == "Quiet market with no recent transitions."
    )
    assert (
        build_summary(
            state=MarketState.TRENDING,
            behavior=MarketBehavior.ACCELERATING,
            transition_changed=True,
        )
        == "Trending market with accelerating behavior."
    )


def test_unchanged_inputs_keep_none_transition_in_context() -> None:
    engine = MarketContextEngine(clock=lambda: 50.0)
    snap = engine.evaluate(
        market_state=_state(MarketState.NORMAL),
        transition=_transition(
            current=MarketState.NORMAL,
            previous=MarketState.NORMAL,
            changed=False,
        ),
        behavior=_behavior(MarketBehavior.STABLE),
        feed_health=_feed(),
        dom_health=_dom(),
        physics=_physics(),
        statistics=_stats(),
    )
    assert snap.transition == NO_TRANSITION
    assert snap.transition_changed is False
    assert "Normal market" in snap.summary


def test_changed_inputs_preserve_transition_fields() -> None:
    engine = MarketContextEngine(clock=lambda: 75.0)
    snap = engine.evaluate(
        market_state=_state(MarketState.VOLATILE, reason="Rapid velocity change"),
        transition=_transition(
            current=MarketState.VOLATILE,
            previous=MarketState.ACTIVE,
            changed=True,
            duration=18.0,
        ),
        behavior=_behavior(MarketBehavior.UNSTABLE, reason="Volatile market condition"),
        feed_health=_feed(status=FeedStatus.STALE, quality=ConnectionQuality.FAIR),
        dom_health=_dom(status=FeedStatus.HEALTHY, quality=ConnectionQuality.GOOD),
        physics=_physics(spread=1.25),
        statistics=_stats(tick_rate=9.0),
    )
    assert snap.transition == "ACTIVE → VOLATILE"
    assert snap.transition_changed is True
    assert snap.transition_duration == 18.0
    assert snap.feed_status == "STALE"
    assert snap.feed_quality == "FAIR"
    assert snap.summary == "Volatile market with unstable behavior."


def test_summary_never_contains_trading_words() -> None:
    cases = [
        (MarketState.UNKNOWN, MarketBehavior.UNKNOWN, False),
        (MarketState.QUIET, MarketBehavior.STABLE, False),
        (MarketState.ACTIVE, MarketBehavior.STABLE, True),
        (MarketState.TRENDING, MarketBehavior.ACCELERATING, True),
        (MarketState.VOLATILE, MarketBehavior.UNSTABLE, True),
        (MarketState.NORMAL, MarketBehavior.DECELERATING, False),
    ]
    banned = ("buy", "sell", "long", "short", "trade", "entry", "exit", "confidence", "probability", "risk")
    for state, behavior, changed in cases:
        summary = build_summary(
            state=state,
            behavior=behavior,
            transition_changed=changed,
        ).lower()
        for word in banned:
            assert word not in summary
