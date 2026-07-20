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
class StatisticsView:
    """STATISTICS section."""

    tick_count: int = 0
    tick_rate: float = 0.0
    running_time_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Complete snapshot rendered each refresh cycle."""

    system: SystemView = field(default_factory=SystemView)
    market: LiveMarketView = field(default_factory=LiveMarketView)
    feed_health: FeedHealthView = field(default_factory=FeedHealthView)
    dom: DomView = field(default_factory=DomView)
    dom_health: DomHealthView = field(default_factory=DomHealthView)
    statistics: StatisticsView = field(default_factory=StatisticsView)
    events: Sequence[str] = ()
