"""Market state observation models (Sprint 6).

Observation only — never emits trading advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarketState(StrEnum):
    """Coarse classification of what the market is doing now."""

    UNKNOWN = "UNKNOWN"
    QUIET = "QUIET"
    NORMAL = "NORMAL"
    ACTIVE = "ACTIVE"
    TRENDING = "TRENDING"
    VOLATILE = "VOLATILE"


class MarketDirection(StrEnum):
    """Signed direction of the current market state (Sprint 35).

    Derived from tick velocity sign. NEUTRAL when velocity is missing or flat.
    """

    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class MarketStateInputs:
    """Read-only observation inputs from existing dashboard snapshots."""

    tick_count: int
    tick_rate: float
    feed_connected: bool
    feed_stale: bool
    connection_quality: str
    spread: float | None
    tick_velocity: float | None
    tick_acceleration: float | None
    dom_update_rate: float = 0.0


@dataclass(frozen=True, slots=True)
class MarketStateSnapshot:
    """Latest market-state observation."""

    state: MarketState
    reason: str
    timestamp: float
    direction: MarketDirection = MarketDirection.NEUTRAL
