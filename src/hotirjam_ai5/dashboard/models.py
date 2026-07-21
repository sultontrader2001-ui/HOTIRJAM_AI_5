"""Immutable dashboard view models.

No trading logic. Market values are optional until a live feed exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Sequence


class EngineStatus(StrEnum):
    """Lifecycle of the local dashboard process."""

    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


class ConnectionStatus(StrEnum):
    """Connectivity to the live NinjaTrader tick feed."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"


class MarketStatus(StrEnum):
    """Whether live market quotes are available to display."""

    WAITING = "WAITING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class FeedStatus(StrEnum):
    """Live feed health derived from tick arrival timing."""

    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"


class ConnectionQuality(StrEnum):
    """Coarse connection quality from recent tick freshness."""

    UNKNOWN = "UNKNOWN"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"


@dataclass(frozen=True, slots=True)
class SystemView:
    """SYSTEM section."""

    engine_status: EngineStatus = EngineStatus.STARTING
    connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    market_status: MarketStatus = MarketStatus.WAITING


@dataclass(frozen=True, slots=True)
class LiveMarketView:
    """LIVE MARKET section.

    Fields stay ``None`` until a verified live tick arrives.
    The renderer shows ``—`` for missing values — never invented prices.
    """

    symbol: str = "MNQ"
    last_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None

    @property
    def spread(self) -> float | None:
        """Ask − bid when both sides are present; otherwise unknown."""
        if self.bid is None or self.ask is None:
            return None
        return self.ask - self.bid


@dataclass(frozen=True, slots=True)
class FeedHealthView:
    """FEED HEALTH section (Sprint 3)."""

    feed_status: FeedStatus = FeedStatus.DISCONNECTED
    connection_quality: ConnectionQuality = ConnectionQuality.UNKNOWN
    last_tick_age_ms: float | None = None
    tick_delay_ms: float | None = None
    average_tick_rate: float = 0.0
    peak_tick_rate: float = 0.0


@dataclass(frozen=True, slots=True)
class DomView:
    """DOM section (Sprint 4)."""

    best_bid_size: int | None = None
    best_ask_size: int | None = None
    total_bid_size: int | None = None
    total_ask_size: int | None = None
    depth_levels: int | None = None
    update_rate: float = 0.0
    status: str | None = None


@dataclass(frozen=True, slots=True)
class DomHealthView:
    """DOM HEALTH section (Sprint 4)."""

    feed_status: FeedStatus = FeedStatus.DISCONNECTED
    connection_quality: ConnectionQuality = ConnectionQuality.UNKNOWN
    last_update_age_ms: float | None = None
    update_rate: float = 0.0
    peak_update_rate: float = 0.0


@dataclass(frozen=True, slots=True)
class PhysicsView:
    """PHYSICS section (Sprint 5)."""

    spread: float | None = None
    mid_price: float | None = None
    tick_velocity: float | None = None
    tick_acceleration: float | None = None


@dataclass(frozen=True, slots=True)
class StatisticsView:
    """STATISTICS section."""

    tick_count: int = 0
    tick_rate: float = 0.0
    running_time_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class MarketStateView:
    """MARKET STATE section (Sprint 6) — observation only."""

    state: str = "UNKNOWN"
    reason: str = "Waiting for market data"


@dataclass(frozen=True, slots=True)
class MarketTransitionView:
    """MARKET TRANSITION section (Sprint 7) — observation only."""

    current_state: str = "UNKNOWN"
    previous_state: str = "—"
    transition: str = "NONE"
    changed: bool = False
    duration_seconds: float = 0.0
    reason: str = "Waiting for market state"


@dataclass(frozen=True, slots=True)
class MarketBehaviorView:
    """MARKET BEHAVIOR section (Sprint 8) — observation only."""

    behavior: str = "UNKNOWN"
    reason: str = "Waiting for market observations"


@dataclass(frozen=True, slots=True)
class MarketContextView:
    """MARKET CONTEXT section (Sprint 9) — aggregator only."""

    summary: str = "Insufficient market context."
    state: str = "UNKNOWN"
    behavior: str = "UNKNOWN"
    transition: str = "NONE"


@dataclass(frozen=True, slots=True)
class DecisionFoundationView:
    """DECISION FOUNDATION section (Sprint 10) — readiness gate only."""

    ready: bool = False
    summary: str = "Waiting for market context."
    blocking_reason: str = "Waiting for market context."


@dataclass(frozen=True, slots=True)
class DecisionIntentView:
    """DECISION INTENT section (Sprint 12) — workflow controller only."""

    intent: str = "WAIT"
    reason: str = "Observation layer is not ready."
    next_step: str = "No further processing."


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Complete snapshot rendered each refresh cycle."""

    system: SystemView = field(default_factory=SystemView)
    market: LiveMarketView = field(default_factory=LiveMarketView)
    feed_health: FeedHealthView = field(default_factory=FeedHealthView)
    dom: DomView = field(default_factory=DomView)
    dom_health: DomHealthView = field(default_factory=DomHealthView)
    physics: PhysicsView = field(default_factory=PhysicsView)
    market_state: MarketStateView = field(default_factory=MarketStateView)
    market_transition: MarketTransitionView = field(default_factory=MarketTransitionView)
    market_behavior: MarketBehaviorView = field(default_factory=MarketBehaviorView)
    market_context: MarketContextView = field(default_factory=MarketContextView)
    decision_foundation: DecisionFoundationView = field(
        default_factory=DecisionFoundationView
    )
    decision_intent: DecisionIntentView = field(default_factory=DecisionIntentView)
    statistics: StatisticsView = field(default_factory=StatisticsView)
    events: Sequence[str] = ()
