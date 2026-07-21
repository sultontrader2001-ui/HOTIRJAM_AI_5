"""Market Context Engine — aggregates existing observation snapshots only."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.dashboard.dom_health import DomHealthSnapshot
from hotirjam_ai5.dashboard.feed_health import FeedHealthSnapshot
from hotirjam_ai5.market_behavior.models import BehaviorSnapshot, MarketBehavior
from hotirjam_ai5.market_context.models import MarketContextSnapshot, StatisticsSnapshot
from hotirjam_ai5.market_state import MarketState, MarketStateSnapshot
from hotirjam_ai5.market_transition.models import NO_TRANSITION, TransitionSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot


class MarketContextEngine:
    """Combines observation snapshots into one immutable context.

    Does not classify markets, detect transitions, or emit trading advice.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = MarketContextSnapshot(
            timestamp=self._clock(),
            state=MarketState.UNKNOWN.value,
            state_reason="Waiting for market data",
            transition=NO_TRANSITION,
            transition_changed=False,
            transition_duration=0.0,
            behavior=MarketBehavior.UNKNOWN.value,
            behavior_reason="Waiting for market observations",
            feed_status="DISCONNECTED",
            feed_quality="UNKNOWN",
            dom_status="DISCONNECTED",
            dom_quality="UNKNOWN",
            tick_rate=0.0,
            spread=None,
            summary="Insufficient market context.",
        )

    def evaluate(
        self,
        *,
        market_state: MarketStateSnapshot,
        transition: TransitionSnapshot,
        behavior: BehaviorSnapshot,
        feed_health: FeedHealthSnapshot,
        dom_health: DomHealthSnapshot,
        physics: PhysicsSnapshot,
        statistics: StatisticsSnapshot,
    ) -> MarketContextSnapshot:
        """Aggregate existing snapshots into one MarketContextSnapshot."""
        summary = build_summary(
            state=market_state.state,
            behavior=behavior.behavior,
            transition_changed=transition.changed,
        )
        self._latest = MarketContextSnapshot(
            timestamp=self._clock(),
            state=market_state.state.value,
            state_reason=market_state.reason,
            transition=transition.transition,
            transition_changed=transition.changed,
            transition_duration=transition.duration_seconds,
            behavior=behavior.behavior.value,
            behavior_reason=behavior.reason,
            feed_status=feed_health.feed_status.value,
            feed_quality=feed_health.connection_quality.value,
            dom_status=dom_health.feed_status.value,
            dom_quality=dom_health.connection_quality.value,
            tick_rate=statistics.tick_rate,
            spread=physics.spread,
            summary=summary,
            state_direction=market_state.direction.value,
            behavior_direction=behavior.direction.value,
            tick_delay_ms=feed_health.tick_delay_ms,
        )
        return self._latest

    def snapshot(self) -> MarketContextSnapshot:
        """Return the latest aggregated context without re-evaluating."""
        return self._latest


def build_summary(
    *,
    state: MarketState,
    behavior: MarketBehavior,
    transition_changed: bool,
) -> str:
    """Build a concise descriptive summary from existing labels only."""
    if state is MarketState.UNKNOWN or behavior is MarketBehavior.UNKNOWN:
        return "Insufficient market context."

    if state is MarketState.ACTIVE and behavior is MarketBehavior.STABLE:
        return "Stable active market."

    if state is MarketState.QUIET and not transition_changed:
        return "Quiet market with no recent transitions."

    state_phrase = {
        MarketState.QUIET: "Quiet market",
        MarketState.NORMAL: "Normal market",
        MarketState.ACTIVE: "Active market",
        MarketState.TRENDING: "Trending market",
        MarketState.VOLATILE: "Volatile market",
    }[state]

    behavior_phrase = {
        MarketBehavior.STABLE: "stable behavior",
        MarketBehavior.ACCELERATING: "accelerating behavior",
        MarketBehavior.DECELERATING: "decelerating behavior",
        MarketBehavior.BALANCED: "balanced behavior",
        MarketBehavior.UNSTABLE: "unstable behavior",
    }.get(behavior)

    if behavior_phrase is not None:
        return f"{state_phrase} with {behavior_phrase}."

    if not transition_changed:
        return f"{state_phrase} with no recent transitions."

    return f"{state_phrase}."
