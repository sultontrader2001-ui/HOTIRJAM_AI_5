"""Market Behavior Engine — observation-only description."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.market_behavior.models import (
    BehaviorInputs,
    BehaviorSnapshot,
    MarketBehavior,
)
from hotirjam_ai5.market_state import MarketState

# Acceleration magnitude thresholds (price units / second^2).
ACCEL_THRESHOLD = 0.5
UNSTABLE_ACCEL_THRESHOLD = 3.0
WIDE_SPREAD_MIN = 1.0

# Activity that is "active but balanced".
BALANCED_RATE_MIN = 2.0


class MarketBehaviorEngine:
    """Describes how the market is behaving from existing observations.

    Does not classify market state, detect transitions, or emit trading advice.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = BehaviorSnapshot(
            behavior=MarketBehavior.UNKNOWN,
            reason="Waiting for market observations",
            timestamp=self._clock(),
        )

    def evaluate(self, inputs: BehaviorInputs) -> BehaviorSnapshot:
        """Describe current behavior from existing snapshots."""
        behavior, reason = classify_behavior(inputs)
        self._latest = BehaviorSnapshot(
            behavior=behavior,
            reason=reason,
            timestamp=self._clock(),
        )
        return self._latest

    def snapshot(self) -> BehaviorSnapshot:
        """Return the latest behavior observation without re-evaluating."""
        return self._latest


def classify_behavior(inputs: BehaviorInputs) -> tuple[MarketBehavior, str]:
    """Classify behavior from existing observations (deterministic).

    Priority: UNKNOWN → UNSTABLE → ACCELERATING → DECELERATING → BALANCED → STABLE
    """
    if (
        inputs.tick_count <= 0
        or not inputs.feed_connected
        or inputs.feed_stale
        or inputs.market_state is MarketState.UNKNOWN
    ):
        return MarketBehavior.UNKNOWN, "Insufficient information"

    acceleration = inputs.tick_acceleration
    velocity = inputs.tick_velocity
    abs_accel = abs(acceleration) if acceleration is not None else None

    if _is_unstable(inputs, abs_accel):
        return MarketBehavior.UNSTABLE, _unstable_reason(inputs, abs_accel)

    if acceleration is not None and acceleration >= ACCEL_THRESHOLD:
        return MarketBehavior.ACCELERATING, "Tick velocity increasing"

    if acceleration is not None and acceleration <= -ACCEL_THRESHOLD:
        return MarketBehavior.DECELERATING, "Tick velocity slowing"

    if _is_accelerating_transition(inputs):
        return MarketBehavior.ACCELERATING, "Activity increasing"

    if _is_decelerating_transition(inputs):
        return MarketBehavior.DECELERATING, "Activity slowing"

    if _is_balanced(inputs, abs_accel):
        return MarketBehavior.BALANCED, "Active but balanced"

    return MarketBehavior.STABLE, "Market activity is steady"


def _is_unstable(inputs: BehaviorInputs, abs_accel: float | None) -> bool:
    if inputs.market_state is MarketState.VOLATILE:
        return True
    if abs_accel is not None and abs_accel >= UNSTABLE_ACCEL_THRESHOLD:
        return True
    if (
        inputs.spread is not None
        and inputs.spread >= WIDE_SPREAD_MIN
        and abs_accel is not None
        and abs_accel >= ACCEL_THRESHOLD
    ):
        return True
    return False


def _unstable_reason(inputs: BehaviorInputs, abs_accel: float | None) -> str:
    if inputs.market_state is MarketState.VOLATILE:
        return "Volatile market condition"
    if abs_accel is not None and abs_accel >= UNSTABLE_ACCEL_THRESHOLD:
        return "Rapid acceleration changes"
    if inputs.spread is not None and inputs.spread >= WIDE_SPREAD_MIN:
        return "Wide spread with rapid change"
    return "Inconsistent market behavior"


def _is_accelerating_transition(inputs: BehaviorInputs) -> bool:
    if not inputs.transition_changed or inputs.previous_state is None:
        return False
    quieter = {MarketState.QUIET, MarketState.NORMAL, MarketState.UNKNOWN}
    more_active = {MarketState.ACTIVE, MarketState.TRENDING, MarketState.VOLATILE}
    return inputs.previous_state in quieter and inputs.market_state in more_active


def _is_decelerating_transition(inputs: BehaviorInputs) -> bool:
    if not inputs.transition_changed or inputs.previous_state is None:
        return False
    more_active = {MarketState.ACTIVE, MarketState.TRENDING, MarketState.VOLATILE}
    quieter = {MarketState.QUIET, MarketState.NORMAL}
    return inputs.previous_state in more_active and inputs.market_state in quieter


def _is_balanced(inputs: BehaviorInputs, abs_accel: float | None) -> bool:
    if inputs.market_state not in (MarketState.ACTIVE, MarketState.NORMAL, MarketState.TRENDING):
        return False
    if inputs.tick_rate < BALANCED_RATE_MIN:
        return False
    if abs_accel is not None and abs_accel >= ACCEL_THRESHOLD:
        return False
    velocity = abs(inputs.tick_velocity) if inputs.tick_velocity is not None else 0.0
    return velocity < 2.0 or inputs.market_state is MarketState.ACTIVE
