"""Tests for Market Transition dashboard wiring."""

from __future__ import annotations

from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.market_state import (
    MarketState,
    MarketStateInputs,
    MarketStateSnapshot,
)


class StubMarketStateEngine:
    def __init__(self, snapshots: list[MarketStateSnapshot]) -> None:
        self._snapshots = iter(snapshots)

    def evaluate(self, inputs: MarketStateInputs) -> MarketStateSnapshot:
        return next(self._snapshots)


def _snapshot(state: MarketState, timestamp: float) -> MarketStateSnapshot:
    return MarketStateSnapshot(
        state=state,
        reason="Observed market condition",
        timestamp=timestamp,
    )


def test_controller_updates_market_transition_from_state_snapshots() -> None:
    state_engine = StubMarketStateEngine(
        [
            _snapshot(MarketState.QUIET, 100.0),
            _snapshot(MarketState.ACTIVE, 118.0),
        ]
    )
    controller = DashboardController(market_state=state_engine)  # type: ignore[arg-type]

    first = controller.snapshot().market_transition
    second = controller.snapshot().market_transition

    assert first.transition == "NONE"
    assert first.changed is False
    assert second.current_state == "ACTIVE"
    assert second.previous_state == "QUIET"
    assert second.transition == "QUIET → ACTIVE"
    assert second.changed is True
    assert second.duration_seconds == 18.0
