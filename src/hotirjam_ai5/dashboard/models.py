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
    statistics: StatisticsView = field(default_factory=StatisticsView)
    events: Sequence[str] = ()
