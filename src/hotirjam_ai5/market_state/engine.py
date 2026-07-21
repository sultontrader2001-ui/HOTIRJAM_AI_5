"""Market State Engine — observation-only classification."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.market_state.classifier import classify_market_state
from hotirjam_ai5.market_state.models import (
    MarketDirection,
    MarketState,
    MarketStateInputs,
    MarketStateSnapshot,
)


def resolve_market_direction(tick_velocity: float | None) -> MarketDirection:
    """Sign the market state from tick velocity (Sprint 35)."""
    if tick_velocity is None or tick_velocity == 0:
        return MarketDirection.NEUTRAL
    return MarketDirection.UP if tick_velocity > 0 else MarketDirection.DOWN


class MarketStateEngine:
    """Classifies market condition from existing live snapshots.

    Does not compute physics, ingest data, or emit trading advice.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = MarketStateSnapshot(
            state=MarketState.UNKNOWN,
            reason="Waiting for market data",
            timestamp=self._clock(),
        )

    def evaluate(self, inputs: MarketStateInputs) -> MarketStateSnapshot:
        """Classify from current observations and store the result."""
        state, reason = classify_market_state(inputs)
        self._latest = MarketStateSnapshot(
            state=state,
            reason=reason,
            timestamp=self._clock(),
            direction=resolve_market_direction(inputs.tick_velocity),
        )
        return self._latest

    def snapshot(self) -> MarketStateSnapshot:
        """Return the latest classification without re-evaluating."""
        return self._latest
