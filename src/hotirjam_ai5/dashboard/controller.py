"""Dashboard controller — assembles state from system, stats, and event log."""

from __future__ import annotations

from collections.abc import Callable
import time

from hotirjam_ai5.dashboard.event_log import EventLog
from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    DashboardState,
    EngineStatus,
    LiveMarketView,
    MarketStatus,
    StatisticsView,
    SystemView,
)
from hotirjam_ai5.dashboard.statistics import SessionStatistics
from hotirjam_ai5.live_data.tick import LiveTick

DEFAULT_STALE_SECONDS = 5.0


class DashboardController:
    """Owns mutable dashboard inputs and produces immutable snapshots.

    Connection becomes CONNECTED only after the first valid live tick.
    """

    def __init__(
        self,
        *,
        symbol: str = "MNQ",
        statistics: SessionStatistics | None = None,
        event_log: EventLog | None = None,
        stale_seconds: float = DEFAULT_STALE_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if stale_seconds <= 0:
            raise ValueError("stale_seconds must be positive")
        self._symbol = symbol.strip().upper() or "MNQ"
        self._statistics = statistics or SessionStatistics(clock=clock)
        self._event_log = event_log or EventLog()
        self._stale_seconds = stale_seconds
        self._clock = clock or time.monotonic
        self._engine_status = EngineStatus.STARTING
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._market_status = MarketStatus.WAITING
        self._market = LiveMarketView(symbol=self._symbol)
        self._last_tick_at: float | None = None

    def start(self) -> None:
        """Mark the engine running and begin waiting for live ticks."""
        self._engine_status = EngineStatus.RUNNING
        self._connection_status = ConnectionStatus.CONNECTING
        self._market_status = MarketStatus.WAITING
        self._event_log.append("Dashboard started")
        self._event_log.append("Connecting — waiting for first live tick")

    def stop(self) -> None:
        """Mark the engine stopped."""
        self._engine_status = EngineStatus.STOPPED
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._event_log.append("Dashboard stopped")

    def on_tick(self, tick: LiveTick) -> None:
        """Apply one validated live tick to the dashboard."""
        if tick.symbol != self._symbol:
            self._event_log.append(f"Ignored tick for unexpected symbol: {tick.symbol}")
            return

        was_connected = self._connection_status is ConnectionStatus.CONNECTED
        self._market = LiveMarketView(
            symbol=tick.symbol,
            last_price=tick.last_price,
            bid=tick.bid,
            ask=tick.ask,
            volume=tick.volume,
        )
        self._statistics.record_tick()
        self._last_tick_at = self._clock()
        self._connection_status = ConnectionStatus.CONNECTED
        self._market_status = MarketStatus.OPEN

        if not was_connected:
            self._event_log.append("Connection established")
        self._event_log.append(f"Tick received (#{self._statistics.tick_count})")

    def check_connection_health(self) -> None:
        """Mark connection lost when no live ticks arrive within the stale window."""
        if self._connection_status is not ConnectionStatus.CONNECTED:
            return
        if self._last_tick_at is None:
            return
        if self._clock() - self._last_tick_at < self._stale_seconds:
            return
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._market_status = MarketStatus.WAITING
        self._event_log.append("Connection lost")

    def snapshot(self) -> DashboardState:
        """Build one immutable dashboard state for rendering."""
        return DashboardState(
            system=SystemView(
                engine_status=self._engine_status,
                connection_status=self._connection_status,
                market_status=self._market_status,
            ),
            market=self._market,
            statistics=StatisticsView(
                tick_count=self._statistics.tick_count,
                tick_rate=self._statistics.tick_rate(),
                running_time_seconds=self._statistics.running_time_seconds(),
            ),
            events=self._event_log.latest(),
        )
