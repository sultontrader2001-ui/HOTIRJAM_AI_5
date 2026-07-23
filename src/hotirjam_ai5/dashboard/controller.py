"""Dashboard controller — assembles state from ticks, DOM, stats, and event log."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import time

from hotirjam_ai5.dashboard.dom_health import DomHealthMonitor
from hotirjam_ai5.dashboard.event_log import EventLog
from hotirjam_ai5.dashboard.feed_health import (
    DEFAULT_DISCONNECT_SECONDS,
    DEFAULT_STALL_SECONDS,
    FeedHealthMonitor,
)
from hotirjam_ai5.dashboard.lifetime_stats import (
    LifetimeStatsStore,
    PeriodStatsSnapshot,
    default_stats_path,
)
from hotirjam_ai5.dashboard.virtual_account import (
    AccountStatusSnapshot,
    VirtualAccountConfig,
    VirtualAccountStore,
    default_account_path,
)
from hotirjam_ai5.trade_planning import TradePlanningEngine, TradePlanningConfig
from hotirjam_ai5.trade_planning.models import TradePlan, TradePlanStatus
from hotirjam_ai5.position_lock import PositionLockManager
from hotirjam_ai5.position_lock.models import PositionLockSnapshot
from hotirjam_ai5.dashboard.models import (
    AccountStatusView,
    ConnectionStatus,
    DashboardState,
    DecisionAssessmentView,
    DecisionEvaluationView,
    DecisionExplanationView,
    DecisionExplainabilityView,
    DecisionFoundationView,
    DecisionIntentView,
    DomHealthView,
    DomView,
    DisplayClockView,
    EngineStatus,
    FeedHealthView,
    FeedStatus,
    LastSignalView,
    LiveMarketView,
    LiquidityView,
    MarketBehaviorView,
    MarketContextView,
    MarketStateView,
    MarketTransitionView,
    MarketStatus,
    MemoryBandView,
    MemoryPanelView,
    PerformanceView,
    PeriodStatsView,
    PhysicsView,
    SignalHistoryRowView,
    StatisticsView,
    SystemPanelView,
    SystemView,
    TradeDecisionView,
    TradePlanView,
    PositionStatusView,
)
from hotirjam_ai5.dashboard.signal_log import SignalLogWriter
from hotirjam_ai5.dashboard.statistics import SessionStatistics
from hotirjam_ai5.dashboard.version_info import git_commit_short, package_version
from hotirjam_ai5.performance.models import PerformanceSnapshot, SignalRecord, SignalResult
from hotirjam_ai5.memory.diagnostics_models import BandSummary, MemoryDiagnosticsReport
from hotirjam_ai5.decision_assessment import DecisionAssessmentEngine
from hotirjam_ai5.decision_evaluation import DecisionEvaluationEngine
from hotirjam_ai5.decision_foundation import DecisionFoundationEngine
from hotirjam_ai5.decision_intent import DecisionIntentEngine
from hotirjam_ai5.liquidity import LiquidityEngine, LiquiditySnapshot
from hotirjam_ai5.live_data.dom import DomSnapshot
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.market_behavior import BehaviorInputs, MarketBehaviorEngine
from hotirjam_ai5.market_context import (
    MarketContextEngine,
    MarketContextSnapshot,
    StatisticsSnapshot as ContextStatisticsSnapshot,
)
from hotirjam_ai5.market_state import (
    MarketStateEngine,
    MarketStateInputs,
    MarketStateSnapshot,
)
from hotirjam_ai5.market_transition import MarketTransitionEngine
from hotirjam_ai5.entry_timing import EntryTimingAuditor
from hotirjam_ai5.performance import PerformanceTracker, format_multi_zone
from hotirjam_ai5.memory import (
    BehaviorAdapter,
    DecisionAdapter,
    LiquidityAdapter,
    MarketMemoryStore,
    MemoryDiagnostics,
    PhysicsAdapter,
    StateAdapter,
    build_memory_diagnostics,
)
from hotirjam_ai5.physics.engine import PhysicsEngine
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision import TradeDecisionEngine
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot
from hotirjam_ai5.trade_decision.policy import empty_decision_explanation

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
        signal_log: SignalLogWriter | None = None,
        feed_health: FeedHealthMonitor | None = None,
        dom_health: DomHealthMonitor | None = None,
        physics: PhysicsEngine | None = None,
        liquidity: LiquidityEngine | None = None,
        market_state: MarketStateEngine | None = None,
        market_transition: MarketTransitionEngine | None = None,
        market_behavior: MarketBehaviorEngine | None = None,
        market_context: MarketContextEngine | None = None,
        decision_foundation: DecisionFoundationEngine | None = None,
        decision_intent: DecisionIntentEngine | None = None,
        decision_evaluation: DecisionEvaluationEngine | None = None,
        decision_assessment: DecisionAssessmentEngine | None = None,
        trade_decision: TradeDecisionEngine | None = None,
        performance: PerformanceTracker | None = None,
        entry_timing: EntryTimingAuditor | None = None,
        memory: MarketMemoryStore | None = None,
        lifetime_stats: LifetimeStatsStore | None = None,
        lifetime_stats_path: Path | str | None = None,
        virtual_account: VirtualAccountStore | None = None,
        virtual_account_path: Path | str | None = None,
        virtual_account_config: VirtualAccountConfig | None = None,
        trade_planning: TradePlanningEngine | None = None,
        trade_planning_path: Path | str | None = None,
        trade_planning_config: TradePlanningConfig | None = None,
        position_lock: PositionLockManager | None = None,
        blocked_signals_path: Path | str | None = None,
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
        self._signal_log = signal_log or SignalLogWriter()
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
        self._liquidity = liquidity or LiquidityEngine(
            clock=wall_clock or time.time
        )
        self._market_state = market_state or MarketStateEngine(clock=wall_clock or time.time)
        self._market_transition = market_transition or MarketTransitionEngine()
        self._market_behavior = market_behavior or MarketBehaviorEngine(
            clock=wall_clock or time.time
        )
        self._market_context = market_context or MarketContextEngine(
            clock=wall_clock or time.time
        )
        self._decision_foundation = decision_foundation or DecisionFoundationEngine(
            clock=wall_clock or time.time
        )
        self._decision_intent = decision_intent or DecisionIntentEngine(
            clock=wall_clock or time.time
        )
        self._decision_evaluation = (
            decision_evaluation
            or DecisionEvaluationEngine(clock=wall_clock or time.time)
        )
        self._decision_assessment = (
            decision_assessment
            or DecisionAssessmentEngine(clock=wall_clock or time.time)
        )
        self._trade_decision = trade_decision or TradeDecisionEngine(
            clock=wall_clock or time.time
        )
        self._performance = performance or PerformanceTracker(
            clock=wall_clock or time.time
        )
        self._entry_timing = entry_timing or EntryTimingAuditor(
            clock=wall_clock or time.time
        )
        # Market Memory is passive — never read by Trade Decision (Sprint 41).
        self._memory = memory or MarketMemoryStore()
        if lifetime_stats is not None:
            self._lifetime = lifetime_stats
        else:
            path = (
                Path(lifetime_stats_path)
                if lifetime_stats_path is not None
                else default_stats_path()
            )
            self._lifetime = LifetimeStatsStore(path)
        if virtual_account is not None:
            self._account = virtual_account
        else:
            account_path = (
                Path(virtual_account_path)
                if virtual_account_path is not None
                else default_account_path()
            )
            self._account = VirtualAccountStore(
                account_path,
                config=virtual_account_config,
            )
        if trade_planning is not None:
            self._trade_planning = trade_planning
        else:
            plan_path = (
                Path(trade_planning_path)
                if trade_planning_path is not None
                else Path("logs") / "trade_plans.json"
            )
            self._trade_planning = TradePlanningEngine(
                config=trade_planning_config,
                clock=wall_clock or time.time,
                path=plan_path,
            )
        self._position_lock = position_lock or PositionLockManager(
            clock=wall_clock or time.time,
            blocked_log_path=blocked_signals_path,
        )
        # Re-sync lock with any restored ACTIVE plan from disk.
        if self._trade_planning.active_plan is not None:
            self._position_lock.on_plan_activated(self._trade_planning.active_plan)
        self._wall_clock = wall_clock or time.time
        self._last_planning_decision: str | None = None
        self._previous_market_state: MarketStateSnapshot | None = None
        self._engine_status = EngineStatus.STARTING
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._market_status = MarketStatus.WAITING
        self._market = LiveMarketView(symbol=self._symbol)
        self._dom = DomView()
        self._physics_view = PhysicsView()
        self._decision_elapsed_ms: list[float] = []
        self._last_signal_memory_effect: str = "--"
        self._last_lifetime_decision: str | None = None

    @property
    def memory_diagnostics(self) -> MemoryDiagnostics:
        """Passive memory diagnostics (not shown on dashboard yet)."""
        return self._memory.diagnostics()

    @property
    def memory_store(self) -> MarketMemoryStore:
        """Bounded memory store for tests / future diagnostics."""
        return self._memory

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
        PhysicsAdapter.record(
            self._memory, physics, timestamp=tick.timestamp
        )
        self._trade_planning.record_price(
            tick.last_price, velocity=physics.tick_velocity
        )
        closed = self._trade_planning.update_price(
            current_price=tick.last_price, timestamp=tick.timestamp
        )
        for plan in closed:
            self._position_lock.on_plan_closed(plan, timestamp=tick.timestamp)
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
        self._liquidity.on_dom(snapshot)
        liquidity = self._liquidity.snapshot()
        if liquidity is not None:
            LiquidityAdapter.record(self._memory, liquidity)
        self._log_dom_transition(previous, FeedStatus.HEALTHY)

    def check_connection_health(self) -> None:
        """Refresh tick and DOM health; log significant transitions."""
        previous = self._feed_health.evaluate()
        current = self._feed_health.feed_status
        self._log_tick_transition(previous, current)

        was_connected = self._connection_status is ConnectionStatus.CONNECTED
        self._sync_system_status_from_feed(current)
        # Clear memory once on the transition into disconnect — not every poll.
        if current is FeedStatus.DISCONNECTED and (
            was_connected or previous is not FeedStatus.DISCONNECTED
        ):
            self._memory.clear()

        dom_previous = self._dom_health.evaluate()
        dom_current = self._dom_health.feed_status
        self._log_dom_transition(dom_previous, dom_current)
        if dom_current is FeedStatus.DISCONNECTED:
            self._liquidity.clear()
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

    def _sync_system_status_from_feed(self, feed_status: FeedStatus) -> None:
        """Align connection/market labels with receive-age feed health.

        Market Status means quote availability (latched Price/Bid/Ask), not a
        short transport quiet gap. WAITING only before the first live quote.
        """
        if feed_status in (FeedStatus.HEALTHY, FeedStatus.STALE):
            self._connection_status = ConnectionStatus.CONNECTED
            self._market_status = MarketStatus.OPEN
            return
        if feed_status is FeedStatus.DISCONNECTED:
            # Pre-first-tick: keep CONNECTING/WAITING from start().
            if self._market.last_price is None:
                return
            self._connection_status = ConnectionStatus.DISCONNECTED
            self._market_status = MarketStatus.OPEN

    def snapshot(self) -> DashboardState:
        """Build one immutable dashboard state for rendering."""
        health = self._feed_health.snapshot()
        dom_health = self._dom_health.snapshot()
        # Keep Market/Connection coherent with receive-age feed health so the
        # UI cannot show WAITING/DISCONNECTED while a fresh tick is latched.
        self._sync_system_status_from_feed(health.feed_status)
        tick_rate = self._statistics.tick_rate()
        tick_count = self._statistics.tick_count
        market_state = self._market_state.evaluate(
            MarketStateInputs(
                tick_count=tick_count,
                tick_rate=tick_rate,
                feed_connected=health.feed_status is not FeedStatus.DISCONNECTED,
                feed_stale=health.feed_status is FeedStatus.STALE,
                connection_quality=health.connection_quality.value,
                spread=self._physics_view.spread,
                tick_velocity=self._physics_view.tick_velocity,
                tick_acceleration=self._physics_view.tick_acceleration,
                dom_update_rate=dom_health.update_rate,
            )
        )
        market_transition = self._market_transition.evaluate(
            market_state,
            self._previous_market_state,
        )
        self._previous_market_state = market_state
        market_behavior = self._market_behavior.evaluate(
            BehaviorInputs(
                market_state=market_state.state,
                transition_changed=market_transition.changed,
                previous_state=market_transition.previous_state,
                tick_count=tick_count,
                tick_rate=tick_rate,
                feed_connected=health.feed_status is not FeedStatus.DISCONNECTED,
                feed_stale=health.feed_status is FeedStatus.STALE,
                spread=self._physics_view.spread,
                tick_velocity=self._physics_view.tick_velocity,
                tick_acceleration=self._physics_view.tick_acceleration,
                dom_update_rate=dom_health.update_rate,
            )
        )
        physics_snapshot = PhysicsSnapshot(
            spread=self._physics_view.spread,
            mid_price=self._physics_view.mid_price,
            tick_velocity=self._physics_view.tick_velocity,
            tick_acceleration=self._physics_view.tick_acceleration,
            tick_count=tick_count,
        )
        market_context = self._market_context.evaluate(
            market_state=market_state,
            transition=market_transition,
            behavior=market_behavior,
            feed_health=health,
            dom_health=dom_health,
            physics=physics_snapshot,
            statistics=ContextStatisticsSnapshot(
                tick_count=tick_count,
                tick_rate=tick_rate,
                running_time_seconds=self._statistics.running_time_seconds(),
            ),
        )
        decision_foundation = self._decision_foundation.evaluate(market_context)
        decision_intent = self._decision_intent.evaluate(decision_foundation)
        decision_evaluation = self._decision_evaluation.evaluate(decision_intent)
        decision_assessment = self._decision_assessment.evaluate(decision_evaluation)
        liquidity_snapshot = None
        if dom_health.feed_status is FeedStatus.HEALTHY:
            liquidity_snapshot = self._liquidity.snapshot()
        # Record State/Behavior before scoring so Memory Diagnostics include them.
        StateAdapter.record(self._memory, market_state)
        BehaviorAdapter.record(self._memory, market_behavior)
        memory_report = build_memory_diagnostics(self._memory)
        decision_started = time.perf_counter()
        trade_decision = self._trade_decision.evaluate(
            decision_assessment,
            market_context,
            physics_snapshot,
            liquidity_snapshot,
            memory_diagnostics=memory_report,
        )
        self._decision_elapsed_ms.append(
            (time.perf_counter() - decision_started) * 1000.0
        )
        if len(self._decision_elapsed_ms) > 200:
            self._decision_elapsed_ms = self._decision_elapsed_ms[-200:]
        # Decision stream append after scoring — does not feed this evaluation.
        DecisionAdapter.record(self._memory, trade_decision)
        self._statistics.record_decision(trade_decision.decision.value)
        if trade_decision.decision is TradeDecision.BUY_INTERNAL:
            self._last_signal_memory_effect = _memory_effect_label(
                trade_decision, side="BUY"
            )
            self._log_buy_internal(
                trade_decision,
                market_context=market_context,
                physics=physics_snapshot,
                liquidity=liquidity_snapshot,
            )
        elif trade_decision.decision is TradeDecision.SELL_INTERNAL:
            self._last_signal_memory_effect = _memory_effect_label(
                trade_decision, side="SELL"
            )
            self._log_sell_internal(
                trade_decision,
                market_context=market_context,
                physics=physics_snapshot,
                liquidity=liquidity_snapshot,
            )
        # Analytics only — observes Trade Decision; never modifies it.
        recorded = self._performance.observe(
            trade_decision,
            symbol=self._symbol,
            current_price=self._market.last_price,
            market_context=market_context,
            physics=physics_snapshot,
            liquidity=liquidity_snapshot,
            timestamp=trade_decision.timestamp,
        )
        self._entry_timing.observe(
            trade_decision,
            symbol=self._symbol,
            current_price=self._market.last_price,
            timestamp=trade_decision.timestamp,
        )
        # Close ACTIVE plans on TP/SL before gating a new plan.
        closed_now = self._trade_planning.update_price(
            current_price=self._market.last_price,
            timestamp=trade_decision.timestamp,
        )
        for closed_plan in closed_now:
            self._position_lock.on_plan_closed(
                closed_plan, timestamp=trade_decision.timestamp
            )
        # Position Lock gates new Trade Plans; market analysis continues.
        decision_value = trade_decision.decision.value
        allow_new = self._position_lock.allows_new_plan()
        is_edge = decision_value != self._last_planning_decision
        if (
            decision_value
            in (
                TradeDecision.BUY_INTERNAL.value,
                TradeDecision.SELL_INTERNAL.value,
            )
            and is_edge
            and not allow_new
        ):
            active = self._trade_planning.active_plan
            active_id = (
                active.plan_id
                if active is not None
                else (self._position_lock.active_trade_id or "--")
            )
            direction = (
                "BUY"
                if trade_decision.decision is TradeDecision.BUY_INTERNAL
                else "SELL"
            )
            self._position_lock.record_blocked(
                direction=direction,
                active_trade_id=active_id,
                timestamp=trade_decision.timestamp,
            )
        planned = self._trade_planning.observe(
            trade_decision,
            current_price=self._market.last_price,
            timestamp=trade_decision.timestamp,
            velocity=physics_snapshot.tick_velocity,
            allow_new=allow_new,
        )
        self._last_planning_decision = decision_value
        if planned is not None and planned.status is TradePlanStatus.ACTIVE:
            self._position_lock.on_plan_activated(
                planned, timestamp=trade_decision.timestamp
            )
        if recorded is not None:
            side = (
                "BUY"
                if trade_decision.decision is TradeDecision.BUY_INTERNAL
                else "SELL"
            )
            effect = _memory_effect_label(trade_decision, side=side)
            self._lifetime.note_open(recorded.signal_id, effect)
        # Edge-count NO_TRADE so lifetime counters match signal-style semantics.
        if (
            trade_decision.decision is TradeDecision.NO_TRADE
            and self._last_lifetime_decision != TradeDecision.NO_TRADE.value
        ):
            self._lifetime.record_no_trade(trade_decision.timestamp)
        self._last_lifetime_decision = decision_value
        self._lifetime.sync_completed(self._performance, self._entry_timing)
        self._lifetime.flush()
        # Virtual account updates from Trade Plan TP/SL closes (Sprint 49).
        self._account.sync_from_trade_plans(self._trade_planning.closed_plans)
        self._account.flush()
        now_epoch = self._wall_clock()
        lifetime_views = self._lifetime.build_views(
            now_epoch=now_epoch,
            pending_records=self._performance.records,
        )
        account_snapshot = self._account.build_snapshot(now_epoch=now_epoch)
        performance = self._performance.snapshot()
        records = self._performance.records
        last_result = "--"
        if records:
            last_result = records[-1].result.value
        timing_summary = self._entry_timing.summary()
        display_clock = format_multi_zone(now_epoch)
        if liquidity_snapshot is None:
            liquidity_view = LiquidityView()
        else:
            liquidity_view = LiquidityView(
                shift=str(liquidity_snapshot.liquidity_shift),
                imbalance=str(liquidity_snapshot.dom_imbalance),
            )
        store_diag = memory_report.store
        avg_decision_ms = None
        if self._decision_elapsed_ms:
            avg_decision_ms = sum(self._decision_elapsed_ms) / len(
                self._decision_elapsed_ms
            )
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
            market_state=MarketStateView(
                state=market_state.state.value,
                reason=market_state.reason,
            ),
            market_transition=MarketTransitionView(
                current_state=market_transition.current_state.value,
                previous_state=(
                    market_transition.previous_state.value
                    if market_transition.previous_state is not None
                    else "--"
                ),
                transition=market_transition.transition,
                changed=market_transition.changed,
                duration_seconds=market_transition.duration_seconds,
                reason=market_transition.reason,
            ),
            market_behavior=MarketBehaviorView(
                behavior=market_behavior.behavior.value,
                reason=market_behavior.reason,
            ),
            market_context=MarketContextView(
                summary=market_context.summary,
                state=market_context.state,
                behavior=market_context.behavior,
                transition=market_context.transition,
            ),
            decision_foundation=DecisionFoundationView(
                ready=decision_foundation.ready,
                summary=decision_foundation.summary,
                blocking_reason=decision_foundation.blocking_reason,
            ),
            decision_intent=DecisionIntentView(
                intent=decision_intent.intent.value,
                reason=decision_intent.reason,
                next_step=decision_intent.next_step,
            ),
            decision_evaluation=DecisionEvaluationView(
                status=decision_evaluation.status.value,
                evaluation_allowed=decision_evaluation.evaluation_allowed,
                reason=decision_evaluation.reason,
                next_stage=decision_evaluation.next_stage,
            ),
            decision_assessment=DecisionAssessmentView(
                assessment_state=decision_assessment.assessment_state.value,
                assessment_ready=decision_assessment.assessment_ready,
                reason=decision_assessment.reason,
                next_stage=decision_assessment.next_stage,
            ),
            trade_decision=TradeDecisionView(
                decision=trade_decision.decision.value,
                buy_score=trade_decision.buy_score,
                buy_confidence=trade_decision.buy_confidence,
                sell_score=trade_decision.sell_score,
                sell_confidence=trade_decision.sell_confidence,
                signal_stability=trade_decision.signal_stability.value,
                sell_signal_stability=trade_decision.sell_signal_stability.value,
                decision_readiness=trade_decision.decision_readiness.value,
                sell_decision_readiness=trade_decision.sell_decision_readiness.value,
                reason=trade_decision.reason,
                next_action=trade_decision.next_action,
                explanation=_trade_explanation_view(trade_decision),
                explainability=_trade_explainability_view(trade_decision),
                memory_influence_pct=_memory_influence_pct(trade_decision),
                memory_agreement=_memory_agreement(trade_decision),
                memory_persistence=_memory_persistence(trade_decision),
            ),
            statistics=StatisticsView(
                tick_count=tick_count,
                tick_rate=tick_rate,
                running_time_seconds=self._statistics.running_time_seconds(),
                buy_internal_count=self._statistics.buy_internal_count,
                sell_internal_count=self._statistics.sell_internal_count,
                no_trade_count=self._statistics.no_trade_count,
                buy_internal_frequency=self._statistics.decision_frequency(
                    "BUY_INTERNAL"
                ),
                sell_internal_frequency=self._statistics.decision_frequency(
                    "SELL_INTERNAL"
                ),
                no_trade_frequency=self._statistics.decision_frequency("NO_TRADE"),
            ),
            performance=_performance_view(
                performance,
                records=records,
                last_result=last_result,
                average_mfe=(
                    timing_summary.average_mfe
                    if timing_summary.signal_count > 0
                    else None
                ),
                average_mae=(
                    timing_summary.average_mae
                    if timing_summary.signal_count > 0
                    else None
                ),
            ),
            today_stats=_period_stats_view(lifetime_views.today),
            lifetime_stats=_period_stats_view(lifetime_views.lifetime),
            signal_history=tuple(
                SignalHistoryRowView(
                    index=row.index,
                    time_label=row.time_label,
                    direction=row.direction,
                    entry=row.entry,
                    exit=row.exit,
                    result=row.result,
                    points=row.points,
                    duration_label=row.duration_label,
                    memory_effect=row.memory_effect,
                )
                for row in lifetime_views.history
            ),
            liquidity=liquidity_view,
            display_clock=DisplayClockView(
                new_york=display_clock.new_york,
                tashkent=display_clock.tashkent,
            ),
            memory_panel=_memory_panel_view(memory_report),
            trade_plan=_trade_plan_view(
                self._trade_planning.current_view_plan(),
                current_price=self._market.last_price,
                now=now_epoch,
            ),
            position_status=_position_status_view(
                self._position_lock.snapshot(
                    plan=self._trade_planning.active_plan,
                    current_price=self._market.last_price,
                    now=now_epoch,
                )
            ),
            account_status=_account_status_view(account_snapshot),
            last_signal=_last_signal_view(
                records,
                memory_effect=self._last_signal_memory_effect,
            ),
            system_panel=SystemPanelView(
                memory_records=store_diag.memory_size,
                decision_count=(
                    self._statistics.buy_internal_count
                    + self._statistics.sell_internal_count
                    + self._statistics.no_trade_count
                ),
                version=package_version(),
                git_commit=git_commit_short(),
                memory_usage_pct=store_diag.ring_buffer_usage,
                append_rate=store_diag.average_append_rate,
                average_decision_ms=avg_decision_ms,
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

    def _log_buy_internal(
        self,
        decision: TradeDecisionSnapshot,
        *,
        market_context: MarketContextSnapshot,
        physics: PhysicsSnapshot,
        liquidity: LiquiditySnapshot | None,
    ) -> None:
        """Write every observation-only BUY_INTERNAL to the signal log file.

        Signal entries never reach the on-screen event log.
        """
        state = market_context.state
        behavior = market_context.behavior
        velocity = physics.tick_velocity
        acceleration = physics.tick_acceleration
        shift = getattr(liquidity, "liquidity_shift", "UNKNOWN")
        imbalance = getattr(liquidity, "dom_imbalance", "UNKNOWN")
        mi = decision.memory_influence
        memory_part = ""
        if mi is not None:
            memory_part = (
                f" original_buy={mi.original_buy_score}"
                f" original_sell={mi.original_sell_score}"
                f" memory_adj_buy={mi.buy_delta:+d}"
                f" memory_adj_sell={mi.sell_delta:+d}"
                f" adjusted_buy={mi.adjusted_buy_score}"
                f" adjusted_sell={mi.adjusted_sell_score}"
                f" consensus={mi.consensus}"
                f" agreement={mi.agreement}"
                f" persistence={mi.persistence}"
                f" final={decision.decision.value}"
            )
        self._signal_log.write(
            "BUY_INTERNAL "
            f"timestamp={decision.timestamp:.6f} "
            f"score={decision.buy_score} "
            f"confidence={decision.buy_confidence} "
            f"state={state} "
            f"behavior={behavior} "
            f"physics=velocity:{velocity},acceleration:{acceleration} "
            f"liquidity=shift:{shift},imbalance:{imbalance}"
            f"{memory_part}"
        )

    def _log_sell_internal(
        self,
        decision: TradeDecisionSnapshot,
        *,
        market_context: MarketContextSnapshot,
        physics: PhysicsSnapshot,
        liquidity: LiquiditySnapshot | None,
    ) -> None:
        """Write every observation-only SELL_INTERNAL to the signal log file.

        Signal entries never reach the on-screen event log.
        """
        price = self._market.last_price
        shift = getattr(liquidity, "liquidity_shift", "UNKNOWN")
        imbalance = getattr(liquidity, "dom_imbalance", "UNKNOWN")
        mi = decision.memory_influence
        memory_part = ""
        if mi is not None:
            memory_part = (
                f" original_buy={mi.original_buy_score}"
                f" original_sell={mi.original_sell_score}"
                f" memory_adj_buy={mi.buy_delta:+d}"
                f" memory_adj_sell={mi.sell_delta:+d}"
                f" adjusted_buy={mi.adjusted_buy_score}"
                f" adjusted_sell={mi.adjusted_sell_score}"
                f" consensus={mi.consensus}"
                f" agreement={mi.agreement}"
                f" persistence={mi.persistence}"
                f" final={decision.decision.value}"
            )
        self._signal_log.write(
            "SELL_INTERNAL "
            f"timestamp={decision.timestamp:.6f} "
            f"price={price} "
            f"score={decision.sell_score} "
            f"confidence={decision.sell_confidence} "
            f"state={market_context.state} "
            f"behavior={market_context.behavior} "
            f"physics=velocity:{physics.tick_velocity},"
            f"acceleration:{physics.tick_acceleration} "
            f"liquidity=shift:{shift},imbalance:{imbalance}"
            f"{memory_part}"
        )


def _format_lock_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--"
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _position_status_view(snapshot: PositionLockSnapshot) -> PositionStatusView:
    return PositionStatusView(
        status=snapshot.display_status.value,
        current_trade_id=snapshot.active_trade_id or "--",
        entry=snapshot.entry,
        current_pnl=snapshot.current_pnl,
        duration=_format_lock_duration(snapshot.duration_seconds),
        distance_to_sl=snapshot.distance_to_sl,
        distance_to_tp=snapshot.distance_to_tp,
        new_signals=snapshot.new_signals.value,
        blocked_signals=snapshot.blocked_signals,
        blocked_buy=snapshot.blocked_buy,
        blocked_sell=snapshot.blocked_sell,
        average_active_duration=_format_lock_duration(snapshot.average_active_duration),
    )


def _trade_plan_view(
    plan: TradePlan | None,
    *,
    current_price: float | None = None,
    now: float | None = None,
) -> TradePlanView:
    """Map a Trade Plan into ACTIVE TRADE / LAST TRADE / TRADE PLAN modes.

    Presentation only — never alters planning, decision, or account logic.
    """
    if plan is None:
        return TradePlanView(mode="NONE")

    base = dict(
        direction=plan.direction.value,
        entry=plan.entry_price,
        stop_loss=plan.stop_loss,
        take_profit=plan.take_profit,
        risk=plan.risk_points,
        reward=plan.reward_points,
        risk_reward=plan.risk_reward,
        status=plan.status.value,
    )

    if plan.status is TradePlanStatus.ACTIVE:
        opened = plan.activated_at if plan.activated_at is not None else plan.created_at
        duration = _format_lock_duration(max(0.0, now - opened)) if now is not None else "--"
        current_pnl = None
        dist_sl = None
        dist_tp = None
        if current_price is not None:
            if plan.direction.value == "BUY":
                current_pnl = current_price - plan.entry_price
                dist_sl = current_price - plan.stop_loss
                dist_tp = plan.take_profit - current_price
            else:
                current_pnl = plan.entry_price - current_price
                dist_sl = plan.stop_loss - current_price
                dist_tp = current_price - plan.take_profit
        return TradePlanView(
            mode="ACTIVE",
            current_price=current_price,
            current_pnl=current_pnl,
            duration=duration,
            distance_to_sl=dist_sl,
            distance_to_tp=dist_tp,
            **base,
        )

    if plan.status is TradePlanStatus.CLOSED:
        if plan.result.value == "WIN":
            exit_reason = "TP"
        elif plan.result.value == "LOSS":
            exit_reason = "SL"
        else:
            exit_reason = "MANUAL"
        opened = plan.activated_at if plan.activated_at is not None else plan.created_at
        duration = "--"
        if plan.closed_at is not None:
            duration = _format_lock_duration(max(0.0, plan.closed_at - opened))
        rr_achieved = None
        if plan.points is not None and plan.risk_points > 0:
            rr_achieved = plan.points / plan.risk_points
        return TradePlanView(
            mode="CLOSED",
            exit_price=plan.exit_price,
            exit_reason=exit_reason,
            pnl=plan.points,
            rr_achieved=rr_achieved,
            duration=duration,
            **base,
        )

    return TradePlanView(mode="ACTIVE", **base)


def _account_status_view(snapshot: AccountStatusSnapshot) -> AccountStatusView:
    """Map virtual account snapshot into the ACCOUNT STATUS panel."""
    return AccountStatusView(
        starting_balance=snapshot.starting_balance,
        current_balance=snapshot.current_balance,
        current_equity=snapshot.current_equity,
        today_pnl=snapshot.today_pnl,
        weekly_pnl=snapshot.weekly_pnl,
        monthly_pnl=snapshot.monthly_pnl,
        lifetime_pnl=snapshot.lifetime_pnl,
        profit_target=snapshot.profit_target,
        progress_pct=snapshot.progress_pct,
        remaining_profit=snapshot.remaining_profit,
        risk_status=snapshot.risk_status,
        win_rate=snapshot.win_rate,
        profit_factor=snapshot.profit_factor,
    )


def _period_stats_view(snapshot: PeriodStatsSnapshot) -> PeriodStatsView:
    """Map lifetime store aggregates into dashboard view models."""
    return PeriodStatsView(
        signals=snapshot.signals,
        buy_signals=snapshot.buy_signals,
        sell_signals=snapshot.sell_signals,
        no_trade=snapshot.no_trade,
        wins=snapshot.wins,
        losses=snapshot.losses,
        breakeven=snapshot.breakeven,
        win_rate=snapshot.win_rate,
        average_rr=snapshot.average_rr,
        average_win=snapshot.average_win,
        average_loss=snapshot.average_loss,
        profit_factor=snapshot.profit_factor,
        average_mfe=snapshot.average_mfe,
        average_mae=snapshot.average_mae,
        memory_helped=snapshot.memory_helped,
        memory_hurt=snapshot.memory_hurt,
        memory_no_effect=snapshot.memory_no_effect,
        largest_win=snapshot.largest_win,
        largest_loss=snapshot.largest_loss,
        net_points=snapshot.net_points,
        gross_profit=snapshot.gross_profit,
        gross_loss=snapshot.gross_loss,
        average_signals_per_day=snapshot.average_signals_per_day,
        average_points_per_signal=snapshot.average_points_per_signal,
        memory_accuracy=snapshot.memory_accuracy,
    )


def _memory_influence_pct(trade_decision: TradeDecisionSnapshot) -> float:
    mi = trade_decision.memory_influence
    return 0.0 if mi is None else mi.influence_pct


def _memory_agreement(trade_decision: TradeDecisionSnapshot) -> float:
    mi = trade_decision.memory_influence
    return 0.0 if mi is None else mi.agreement


def _memory_persistence(trade_decision: TradeDecisionSnapshot) -> float:
    mi = trade_decision.memory_influence
    return 0.0 if mi is None else mi.persistence


def _memory_effect_label(trade_decision: TradeDecisionSnapshot, *, side: str) -> str:
    """Presentation-only HELPED / HURT / NO_EFFECT from Memory deltas."""
    mi = trade_decision.memory_influence
    if mi is None or not mi.applied:
        return "NO_EFFECT"
    delta = mi.buy_delta if side == "BUY" else mi.sell_delta
    if delta > 0:
        return "HELPED"
    if delta < 0:
        return "HURT"
    return "NO_EFFECT"


def _band_view(band: BandSummary) -> MemoryBandView:
    return MemoryBandView(
        name=band.name.value,
        direction=band.direction,
        strength=band.strength,
        confidence=band.confidence,
        persistence=band.persistence,
    )


def _memory_panel_view(report: MemoryDiagnosticsReport) -> MemoryPanelView:
    fast, medium, slow = report.bands
    return MemoryPanelView(
        fast=_band_view(fast),
        medium=_band_view(medium),
        slow=_band_view(slow),
        consensus_direction=report.consensus.direction,
        consensus_agreement=report.consensus.agreement,
        consensus_confidence=report.consensus.confidence,
        consensus_status=report.consensus.status.value,
    )


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _last_signal_view(
    records: tuple[SignalRecord, ...],
    *,
    memory_effect: str,
) -> LastSignalView:
    if not records:
        return LastSignalView()
    record = records[-1]
    direction = record.decision.replace("_INTERNAL", "")
    entry = record.entry_time.new_york
    if record.evaluation_time is None:
        exit_time = "--"
        duration = "--"
    else:
        exit_time = record.evaluation_time.new_york
        duration = _format_duration(
            record.evaluation_time.epoch_seconds - record.entry_time.epoch_seconds
        )
    return LastSignalView(
        direction=direction,
        entry_time=entry,
        exit_time=exit_time,
        duration=duration,
        result=record.result.value,
        points=record.points,
        memory_effect=memory_effect if memory_effect else "--",
    )


def _performance_view(
    performance: PerformanceSnapshot,
    *,
    records: tuple[SignalRecord, ...],
    last_result: str,
    average_mfe: float | None,
    average_mae: float | None,
) -> PerformanceView:
    wins = [
        r.points
        for r in records
        if r.result is SignalResult.SUCCESS and r.points is not None
    ]
    losses = [
        r.points
        for r in records
        if r.result is SignalResult.FAILED and r.points is not None
    ]
    average_rr: float | None = None
    profit_factor: float | None = None
    if wins and losses:
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))
        if avg_loss > 0:
            average_rr = avg_win / avg_loss
        gross_loss = abs(sum(losses))
        if gross_loss > 0:
            profit_factor = sum(wins) / gross_loss
    elif wins and not losses:
        profit_factor = None
        average_rr = None

    evaluated = performance.success_count + performance.failed_count
    decision_accuracy = performance.win_rate if evaluated else None
    signals_today = performance.buy_signals + performance.sell_signals

    return PerformanceView(
        buy_signals=performance.buy_signals,
        sell_signals=performance.sell_signals,
        success_count=performance.success_count,
        failed_count=performance.failed_count,
        win_rate=performance.win_rate,
        average_points=performance.average_points,
        last_result=last_result,
        last_signal_decision=performance.last_signal_decision,
        last_signal_utc=performance.last_signal_utc,
        last_signal_new_york=performance.last_signal_new_york,
        last_signal_tashkent=performance.last_signal_tashkent,
        signals_today=signals_today,
        average_mfe=average_mfe,
        average_mae=average_mae,
        average_rr=average_rr,
        profit_factor=profit_factor,
        decision_accuracy=decision_accuracy,
    )


def _trade_explanation_view(
    trade_decision: TradeDecisionSnapshot,
) -> DecisionExplanationView:
    explanation = trade_decision.decision_explanation or empty_decision_explanation()
    return DecisionExplanationView(
        assessment=explanation.assessment.value,
        feed=explanation.feed.value,
        market_state=explanation.market_state.value,
        behavior=explanation.behavior.value,
        physics=explanation.physics.value,
        liquidity=explanation.liquidity.value,
        signal_stability=explanation.signal_stability.value,
        readiness=explanation.readiness.value,
        summary=explanation.summary,
    )


def _trade_explainability_view(
    trade_decision: TradeDecisionSnapshot,
) -> DecisionExplainabilityView:
    """Map snapshot explainability — presentation only, no recalculation."""
    expl = trade_decision.explainability
    if expl is None:
        return DecisionExplainabilityView(
            headline="NO TRADE",
            buy_total=trade_decision.buy_score,
            sell_total=trade_decision.sell_score,
        )
    buy_lines = tuple(
        f"{line.label:<14} +{line.points}" for line in expl.buy_contributions
    )
    sell_lines = tuple(
        f"{line.label:<14} +{line.points}" for line in expl.sell_contributions
    )
    return DecisionExplainabilityView(
        headline=expl.headline,
        buy_lines=buy_lines,
        buy_total=expl.buy_total,
        sell_lines=sell_lines,
        sell_total=expl.sell_total,
        checklist=expl.checklist,
        selection_lines=expl.selection_lines,
        buy_detail_lines=expl.buy_detail_lines,
        sell_detail_lines=expl.sell_detail_lines,
        buy_reason=expl.buy_reason,
        sell_reason=expl.sell_reason,
    )
