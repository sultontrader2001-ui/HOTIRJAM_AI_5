"""Dashboard controller — assembles state from ticks, DOM, stats, and event log."""

from __future__ import annotations

from collections.abc import Callable
import time

from hotirjam_ai5.dashboard.dom_health import DomHealthMonitor
from hotirjam_ai5.dashboard.event_log import EventLog
from hotirjam_ai5.dashboard.feed_health import (
    DEFAULT_DISCONNECT_SECONDS,
    DEFAULT_STALL_SECONDS,
    FeedHealthMonitor,
)
from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    DashboardState,
    DomHealthView,
    DomView,
    EngineStatus,
    FeedHealthView,
    FeedStatus,
    LiveMarketView,
    MarketStatus,
    PhysicsView,
    StatisticsView,
    SystemView,
)
from hotirjam_ai5.dashboard.statistics import SessionStatistics
from hotirjam_ai5.live_data.dom import DomSnapshot
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.physics.engine import PhysicsEngine

# Backward-compatible alias used by CLI / older call sites.
DEFAULT_STALE_SECONDS = DEFAULT_DISCONNECT_SECONDS
DASHBOARD_EVENT_LOG_CAPACITY = 5


class DashboardController:
    """Owns mutable dashboard inputs and produces immutable snapshots.

    Connection becomes CONNECTED only after the first valid live tick.
    LOG records only significant tick/DOM feed events.
    """

    def __init__(
        self,
        *,
        symbol: str = "MNQ",
        statistics: SessionStatistics | None = None,
        event_log: EventLog | None = None,
        feed_health: FeedHealthMonitor | None = None,
        dom_health: DomHealthMonitor | None = None,
        physics: PhysicsEngine | None = None,
        stale_seconds: float = DEFAULT_DISCONNECT_SECONDS,
        stall_seconds: float = DEFAULT_STALL_SECONDS,
        clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], float] | None = None,
    ) -> None:
        if stale_seconds <= 0:
            raise ValueError("stale_seconds must be positive")
        self._symbol = symbol.strip().upper() or "MNQ"
        self._clock = clock or time.monotonic
        self._statistics = statistics or SessionStatistics(clock=self._clock)
        self._event_log = event_log or EventLog(capacity=DASHBOARD_EVENT_LOG_CAPACITY)
        self._feed_health = feed_health or FeedHealthMonitor(
            stall_seconds=stall_seconds,
            disconnect_seconds=stale_seconds,
            clock=self._clock,
            wall_clock=wall_clock,
        )
        self._dom_health = dom_health or DomHealthMonitor(
            stall_seconds=stall_seconds,
            disconnect_seconds=stale_seconds,
            clock=self._clock,
        )
        self._physics = physics or PhysicsEngine()
        self._engine_status = EngineStatus.STARTING
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._market_status = MarketStatus.WAITING
        self._market = LiveMarketView(symbol=self._symbol)
        self._dom = DomView()
        self._physics_view = PhysicsView()

    def start(self) -> None:
        """Mark the engine running and begin waiting for live ticks."""
        self._engine_status = EngineStatus.RUNNING
        self._connection_status = ConnectionStatus.CONNECTING
        self._market_status = MarketStatus.WAITING

    def stop(self) -> None:
        """Mark the engine stopped."""
        self._engine_status = EngineStatus.STOPPED
        self._connection_status = ConnectionStatus.DISCONNECTED

    def on_tick(self, tick: LiveTick) -> None:
        """Apply one validated live tick to the dashboard."""
        if tick.symbol != self._symbol:
            return

        previous = self._feed_health.record_tick(tick)
        self._market = LiveMarketView(
            symbol=tick.symbol,
            last_price=tick.last_price,
            bid=tick.bid,
            ask=tick.ask,
            volume=tick.volume,
        )
        physics = self._physics.on_tick(tick)
        self._physics_view = PhysicsView(
            spread=physics.spread,
            mid_price=physics.mid_price,
            tick_velocity=physics.tick_velocity,
            tick_acceleration=physics.tick_acceleration,
        )
        self._statistics.record_tick()
        self._connection_status = ConnectionStatus.CONNECTED
        self._market_status = MarketStatus.OPEN
        self._log_tick_transition(previous, FeedStatus.HEALTHY)

    def on_dom(self, snapshot: DomSnapshot) -> None:
        """Apply one validated live DOM snapshot to the dashboard."""
        if snapshot.instrument != self._symbol:
            return

        previous = self._dom_health.record_update()
        health = self._dom_health.snapshot()
        self._dom = DomView(
            best_bid_size=snapshot.best_bid_size,
            best_ask_size=snapshot.best_ask_size,
            total_bid_size=snapshot.total_bid_size,
            total_ask_size=snapshot.total_ask_size,
            depth_levels=snapshot.depth_levels,
            update_rate=health.update_rate,
            status=snapshot.status,
        )
        self._log_dom_transition(previous, FeedStatus.HEALTHY)

    def check_connection_health(self) -> None:
        """Refresh tick and DOM health; log significant transitions."""
        previous = self._feed_health.evaluate()
        current = self._feed_health.feed_status
        self._log_tick_transition(previous, current)

        if current is FeedStatus.DISCONNECTED:
            if self._connection_status is ConnectionStatus.CONNECTED:
                self._connection_status = ConnectionStatus.DISCONNECTED
                self._market_status = MarketStatus.WAITING
        elif current in (FeedStatus.HEALTHY, FeedStatus.STALE):
            self._connection_status = ConnectionStatus.CONNECTED
            self._market_status = MarketStatus.OPEN

        dom_previous = self._dom_health.evaluate()
        dom_current = self._dom_health.feed_status
        self._log_dom_transition(dom_previous, dom_current)
        if self._dom.total_bid_size is not None:
            health = self._dom_health.snapshot()
            self._dom = DomView(
                best_bid_size=self._dom.best_bid_size,
                best_ask_size=self._dom.best_ask_size,
                total_bid_size=self._dom.total_bid_size,
                total_ask_size=self._dom.total_ask_size,
                depth_levels=self._dom.depth_levels,
                update_rate=health.update_rate,
                status=self._dom.status,
            )

    def snapshot(self) -> DashboardState:
        """Build one immutable dashboard state for rendering."""
        health = self._feed_health.snapshot()
        dom_health = self._dom_health.snapshot()
        return DashboardState(
            system=SystemView(
                engine_status=self._engine_status,
                connection_status=self._connection_status,
                market_status=self._market_status,
            ),
            market=self._market,
            feed_health=FeedHealthView(
                feed_status=health.feed_status,
                connection_quality=health.connection_quality,
                last_tick_age_ms=health.last_tick_age_ms,
                tick_delay_ms=health.tick_delay_ms,
                average_tick_rate=health.average_tick_rate,
                peak_tick_rate=health.peak_tick_rate,
            ),
            dom=self._dom,
            dom_health=DomHealthView(
                feed_status=dom_health.feed_status,
                connection_quality=dom_health.connection_quality,
                last_update_age_ms=dom_health.last_update_age_ms,
                update_rate=dom_health.update_rate,
                peak_update_rate=dom_health.peak_update_rate,
            ),
            physics=self._physics_view,
            statistics=StatisticsView(
                tick_count=self._statistics.tick_count,
                tick_rate=self._statistics.tick_rate(),
                running_time_seconds=self._statistics.running_time_seconds(),
            ),
            events=self._event_log.latest(),
        )

    def _log_tick_transition(self, previous: FeedStatus, current: FeedStatus) -> None:
        if previous is current:
            return
        if current is FeedStatus.HEALTHY:
            if previous is FeedStatus.STALE:
                self._event_log.append("Feed resumed")
            else:
                self._event_log.append("Connected")
            return
        if current is FeedStatus.STALE and previous is FeedStatus.HEALTHY:
            self._event_log.append("Feed stalled")
            return
        if current is FeedStatus.DISCONNECTED and previous is not FeedStatus.DISCONNECTED:
            self._event_log.append("Connection lost")

    def _log_dom_transition(self, previous: FeedStatus, current: FeedStatus) -> None:
        if previous is current:
            return
        if current is FeedStatus.HEALTHY:
            if previous is FeedStatus.STALE:
                self._event_log.append("DOM resumed")
            else:
                self._event_log.append("DOM connected")
            return
        if current is FeedStatus.STALE and previous is FeedStatus.HEALTHY:
            self._event_log.append("DOM stalled")
            return
        if current is FeedStatus.DISCONNECTED and previous is not FeedStatus.DISCONNECTED:
            self._event_log.append("DOM connection lost")
