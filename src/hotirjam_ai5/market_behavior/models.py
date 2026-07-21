"""Market behavior observation models (Sprint 8).

Observation only — never emits trading advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.market_state import MarketState


class MarketBehavior(StrEnum):
    """How the market is currently behaving."""

    UNKNOWN = "UNKNOWN"
    STABLE = "STABLE"
    ACCELERATING = "ACCELERATING"
    DECELERATING = "DECELERATING"
    BALANCED = "BALANCED"
    UNSTABLE = "UNSTABLE"


class BehaviorDirection(StrEnum):
    """Signed direction of the current behavior (Sprint 35).

    Derived from tick velocity sign. NEUTRAL when velocity is missing or flat.
    """

    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class BehaviorInputs:
    """Read-only inputs assembled from existing snapshots."""

    market_state: MarketState
    transition_changed: bool
    previous_state: MarketState | None
    tick_count: int
    tick_rate: float
    feed_connected: bool
    feed_stale: bool
    spread: float | None
    tick_velocity: float | None
    tick_acceleration: float | None
    dom_update_rate: float = 0.0


@dataclass(frozen=True, slots=True)
class BehaviorSnapshot:
    """Latest market-behavior observation."""

    behavior: MarketBehavior
    reason: str
    timestamp: float
    direction: BehaviorDirection = BehaviorDirection.NEUTRAL
