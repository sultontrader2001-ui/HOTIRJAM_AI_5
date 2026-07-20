"""Deterministic market-state classifier (observation only)."""

from __future__ import annotations

from hotirjam_ai5.market_state.models import MarketState, MarketStateInputs

# Tick-rate thresholds (ticks / second).
QUIET_RATE_MAX = 1.0
NORMAL_RATE_MAX = 5.0
ACTIVE_RATE_MIN = 5.0

# Physics magnitude thresholds (price units / second, / second^2).
TREND_VELOCITY_MIN = 2.0
VOLATILE_ACCELERATION_MIN = 3.0
VOLATILE_VELOCITY_MIN = 4.0
WIDE_SPREAD_MIN = 1.0


def classify_market_state(inputs: MarketStateInputs) -> tuple[MarketState, str]:
    """Classify current market condition from existing observations.

    Priority (most specific first):
    UNKNOWN → VOLATILE → TRENDING → ACTIVE → QUIET → NORMAL
    """
    if inputs.tick_count <= 0 or not inputs.feed_connected:
        return MarketState.UNKNOWN, "Insufficient market data"

    if inputs.feed_stale:
        return MarketState.UNKNOWN, "Feed stale — waiting for fresh ticks"

    velocity = abs(inputs.tick_velocity) if inputs.tick_velocity is not None else None
    acceleration = (
        abs(inputs.tick_acceleration) if inputs.tick_acceleration is not None else None
    )
    spread = inputs.spread

    if _is_volatile(velocity, acceleration, spread):
        return MarketState.VOLATILE, _volatile_reason(velocity, acceleration, spread)

    if velocity is not None and velocity >= TREND_VELOCITY_MIN:
        if acceleration is None or acceleration < VOLATILE_ACCELERATION_MIN:
            return MarketState.TRENDING, "Sustained price velocity"

    if inputs.tick_rate >= ACTIVE_RATE_MIN:
        return MarketState.ACTIVE, "Tick activity increasing"

    if inputs.tick_rate <= QUIET_RATE_MAX:
        return MarketState.QUIET, "Low tick activity"

    if QUIET_RATE_MAX < inputs.tick_rate < ACTIVE_RATE_MIN:
        return MarketState.NORMAL, "Steady market activity"

    return MarketState.NORMAL, "Steady market activity"


def _is_volatile(
    velocity: float | None,
    acceleration: float | None,
    spread: float | None,
) -> bool:
    if acceleration is not None and acceleration >= VOLATILE_ACCELERATION_MIN:
        return True
    if (
        velocity is not None
        and velocity >= VOLATILE_VELOCITY_MIN
        and acceleration is not None
        and acceleration >= TREND_VELOCITY_MIN
    ):
        return True
    if spread is not None and spread >= WIDE_SPREAD_MIN:
        if velocity is not None and velocity >= TREND_VELOCITY_MIN:
            return True
    return False


def _volatile_reason(
    velocity: float | None,
    acceleration: float | None,
    spread: float | None,
) -> str:
    if acceleration is not None and acceleration >= VOLATILE_ACCELERATION_MIN:
        return "Rapid velocity change"
    if spread is not None and spread >= WIDE_SPREAD_MIN:
        return "Wide spread with elevated velocity"
    return "Unstable price movement"
