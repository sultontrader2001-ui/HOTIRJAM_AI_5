"""Market Transition Engine — retrospective observation only."""

from __future__ import annotations

from hotirjam_ai5.market_state import MarketStateSnapshot
from hotirjam_ai5.market_transition.models import NO_TRANSITION, TransitionSnapshot


class MarketTransitionEngine:
    """Reports changes between consecutive market-state snapshots.

    The engine does not inspect market data, classify states, or forecast.
    """

    def __init__(self) -> None:
        self._state_started_at: float | None = None
        self._latest: TransitionSnapshot | None = None

    def evaluate(
        self,
        current: MarketStateSnapshot,
        previous: MarketStateSnapshot | None,
    ) -> TransitionSnapshot:
        """Compare current and previous observations."""
        if previous is None:
            self._state_started_at = current.timestamp
            reason = "First market state observed"
            snapshot = TransitionSnapshot(
                current_state=current.state,
                previous_state=None,
                transition=NO_TRANSITION,
                changed=False,
                duration_seconds=0.0,
                reason=reason,
                timestamp=current.timestamp,
            )
            self._latest = snapshot
            return snapshot

        if self._state_started_at is None:
            self._state_started_at = previous.timestamp

        duration = max(0.0, current.timestamp - self._state_started_at)
        changed = current.state is not previous.state

        if changed:
            transition = f"{previous.state.value} → {current.state.value}"
            reason = f"Market state changed from {previous.state.value} to {current.state.value}"
            self._state_started_at = current.timestamp
        else:
            transition = NO_TRANSITION
            reason = f"Market state remains {current.state.value}"

        snapshot = TransitionSnapshot(
            current_state=current.state,
            previous_state=previous.state,
            transition=transition,
            changed=changed,
            duration_seconds=duration,
            reason=reason,
            timestamp=current.timestamp,
        )
        self._latest = snapshot
        return snapshot

    def snapshot(self) -> TransitionSnapshot | None:
        """Return the latest transition observation."""
        return self._latest
