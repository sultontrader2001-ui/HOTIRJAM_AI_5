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
    buy_internal_count: int = 0
    sell_internal_count: int = 0
    no_trade_count: int = 0
    buy_internal_frequency: float = 0.0
    sell_internal_frequency: float = 0.0
    no_trade_frequency: float = 0.0


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
class DecisionEvaluationView:
    """DECISION EVALUATION section (Sprint 13) — evaluation lifecycle only."""

    status: str = "IDLE"
    evaluation_allowed: bool = False
    reason: str = "Evaluation not started."
    next_stage: str = "Continue Observation"


@dataclass(frozen=True, slots=True)
class DecisionAssessmentView:
    """DECISION ASSESSMENT section (Sprint 14) — standardization only."""

    assessment_state: str = "REVIEW"
    assessment_ready: bool = False
    reason: str = "Evaluation complete, awaiting final decision."
    next_stage: str = "Decision Assessment Engine"


@dataclass(frozen=True, slots=True)
class DecisionExplanationView:
    """Structured WHY for TRADE DECISION."""

    assessment: str = "UNKNOWN"
    feed: str = "UNKNOWN"
    market_state: str = "UNKNOWN"
    behavior: str = "UNKNOWN"
    physics: str = "UNKNOWN"
    liquidity: str = "UNKNOWN"
    signal_stability: str = "UNKNOWN"
    readiness: str = "UNKNOWN"
    summary: str = "Decision Readiness is UNKNOWN."


@dataclass(frozen=True, slots=True)
class DecisionExplainabilityView:
    """DECISION EXPLANATION section — real score evidence (Sprint 36/38)."""

    headline: str = "NO TRADE"
    buy_lines: tuple[str, ...] = ()
    buy_total: int = 0
    sell_lines: tuple[str, ...] = ()
    sell_total: int = 0
    checklist: tuple[str, ...] = ()
    selection_lines: tuple[str, ...] = ()
    buy_detail_lines: tuple[str, ...] = ()
    sell_detail_lines: tuple[str, ...] = ()
    buy_reason: str = ""
    sell_reason: str = ""


@dataclass(frozen=True, slots=True)
class TradeDecisionView:
    """TRADE DECISION section — observation-only internal activation."""

    decision: str = "NO_TRADE"
    buy_score: int = 0
    buy_confidence: int = 0
    sell_score: int = 0
    sell_confidence: int = 0
    signal_stability: str = "UNSTABLE"
    sell_signal_stability: str = "UNSTABLE"
    decision_readiness: str = "UNKNOWN"
    sell_decision_readiness: str = "UNKNOWN"
    reason: str = "Decision Readiness is UNKNOWN."
    next_action: str = "Execution Engine"
    explanation: DecisionExplanationView = field(
        default_factory=DecisionExplanationView
    )
    explainability: DecisionExplainabilityView = field(
        default_factory=DecisionExplainabilityView
    )
    # Sprint 44 — Memory influence diagnostics (presentation only).
    memory_influence_pct: float = 0.0
    memory_agreement: float = 0.0
    memory_persistence: float = 0.0


@dataclass(frozen=True, slots=True)
class MemoryBandView:
    """One Memory observation band for MEMORY section (presentation only)."""

    name: str = "FAST"
    direction: str = "--"
    strength: float | None = None
    confidence: float | None = None
    persistence: float | None = None


@dataclass(frozen=True, slots=True)
class MemoryPanelView:
    """MEMORY section — read-only projection of Memory Diagnostics."""

    fast: MemoryBandView = field(default_factory=lambda: MemoryBandView(name="FAST"))
    medium: MemoryBandView = field(
        default_factory=lambda: MemoryBandView(name="MEDIUM")
    )
    slow: MemoryBandView = field(default_factory=lambda: MemoryBandView(name="SLOW"))
    consensus_direction: str = "--"
    consensus_agreement: float | None = None
    consensus_confidence: float | None = None
    consensus_status: str = "--"


@dataclass(frozen=True, slots=True)
class LastSignalView:
    """LAST SIGNAL section — presentation only (retained for verbose / compat)."""

    direction: str = "--"
    entry_time: str = "--"
    exit_time: str = "--"
    duration: str = "--"
    result: str = "--"
    points: float | None = None
    memory_effect: str = "--"  # HELPED | HURT | NO_EFFECT | --


@dataclass(frozen=True, slots=True)
class PerformanceView:
    """Legacy PERFORMANCE snapshot (Sprint 32/45) — kept for verbose / compat."""

    buy_signals: int = 0
    sell_signals: int = 0
    success_count: int = 0
    failed_count: int = 0
    win_rate: float = 0.0
    average_points: float = 0.0
    last_result: str = "--"
    last_signal_decision: str = "--"
    last_signal_utc: str = "--"
    last_signal_new_york: str = "--"
    last_signal_tashkent: str = "--"
    signals_today: int = 0
    average_mfe: float | None = None
    average_mae: float | None = None
    average_rr: float | None = None
    profit_factor: float | None = None
    decision_accuracy: float | None = None


@dataclass(frozen=True, slots=True)
class PeriodStatsView:
    """TODAY or LIFETIME panel — None fields render as ``--`` (Sprint 46)."""

    signals: int | None = None
    buy_signals: int | None = None
    sell_signals: int | None = None
    no_trade: int | None = None
    wins: int | None = None
    losses: int | None = None
    breakeven: int | None = None
    win_rate: float | None = None
    average_rr: float | None = None
    average_win: float | None = None
    average_loss: float | None = None
    profit_factor: float | None = None
    average_mfe: float | None = None
    average_mae: float | None = None
    memory_helped: int | None = None
    memory_hurt: int | None = None
    memory_no_effect: int | None = None
    largest_win: float | None = None
    largest_loss: float | None = None
    net_points: float | None = None
    gross_profit: float | None = None
    gross_loss: float | None = None
    average_signals_per_day: float | None = None
    average_points_per_signal: float | None = None
    memory_accuracy: float | None = None


@dataclass(frozen=True, slots=True)
class SignalHistoryRowView:
    """One SIGNAL HISTORY row (Sprint 46)."""

    index: int = 0
    time_label: str = "--"
    direction: str = "--"
    entry: float | None = None
    exit: float | None = None
    result: str = "--"
    points: float | None = None
    duration_label: str = "--"
    memory_effect: str = "--"


@dataclass(frozen=True, slots=True)
class SystemPanelView:
    """SYSTEM section (Sprint 46 — compact operational strip)."""

    memory_records: int = 0
    decision_count: int = 0
    version: str = "--"
    git_commit: str = "--"
    # Retained for verbose / older call sites.
    memory_usage_pct: float | None = None
    append_rate: float | None = None
    average_decision_ms: float | None = None


@dataclass(frozen=True, slots=True)
class AccountStatusView:
    """ACCOUNT STATUS section — virtual prop account (Sprint 47/48)."""

    starting_balance: float | None = None
    current_balance: float | None = None
    current_equity: float | None = None
    today_pnl: float | None = None
    weekly_pnl: float | None = None
    monthly_pnl: float | None = None
    lifetime_pnl: float | None = None
    profit_target: float | None = None
    progress_pct: float | None = None
    remaining_profit: float | None = None
    risk_status: str | None = None
    win_rate: float | None = None
    profit_factor: float | None = None


@dataclass(frozen=True, slots=True)
class PositionStatusView:
    """POSITION STATUS section — lock / active trade (Sprint 50)."""

    status: str = "IDLE"  # IDLE | ACTIVE | BLOCKED
    current_trade_id: str = "--"
    entry: float | None = None
    current_pnl: float | None = None
    duration: str = "--"
    distance_to_sl: float | None = None
    distance_to_tp: float | None = None
    new_signals: str = "ALLOWED"  # ALLOWED | BLOCKED
    blocked_signals: int = 0
    blocked_buy: int = 0
    blocked_sell: int = 0
    average_active_duration: str = "--"


@dataclass(frozen=True, slots=True)
class TradePlanView:
    """TRADE PLAN / ACTIVE TRADE / LAST TRADE section (Sprint 49/50.1).

    ``mode`` selects the presentation: NONE (never traded), ACTIVE (live
    trade), or CLOSED (last completed trade). Presentation only.
    """

    mode: str = "NONE"  # NONE | ACTIVE | CLOSED
    direction: str = "--"
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk: float | None = None
    reward: float | None = None
    risk_reward: float | None = None
    status: str = "--"
    # ACTIVE-mode extras (live context)
    current_price: float | None = None
    current_pnl: float | None = None
    duration: str = "--"
    distance_to_sl: float | None = None
    distance_to_tp: float | None = None
    # CLOSED-mode extras (historical outcome)
    exit_price: float | None = None
    exit_reason: str = "--"  # TP | SL | MANUAL
    pnl: float | None = None
    rr_achieved: float | None = None


@dataclass(frozen=True, slots=True)
class LiquidityView:
    """Liquidity summary for AI STATUS (presentation only)."""

    shift: str = "--"
    imbalance: str = "--"


@dataclass(frozen=True, slots=True)
class DisplayClockView:
    """Wall-clock times for MARKET section (presentation only)."""

    new_york: str = "--"
    tashkent: str = "--"


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
    decision_evaluation: DecisionEvaluationView = field(
        default_factory=DecisionEvaluationView
    )
    decision_assessment: DecisionAssessmentView = field(
        default_factory=DecisionAssessmentView
    )
    trade_decision: TradeDecisionView = field(default_factory=TradeDecisionView)
    statistics: StatisticsView = field(default_factory=StatisticsView)
    performance: PerformanceView = field(default_factory=PerformanceView)
    today_stats: PeriodStatsView = field(default_factory=PeriodStatsView)
    lifetime_stats: PeriodStatsView = field(default_factory=PeriodStatsView)
    signal_history: tuple[SignalHistoryRowView, ...] = ()
    liquidity: LiquidityView = field(default_factory=LiquidityView)
    display_clock: DisplayClockView = field(default_factory=DisplayClockView)
    memory_panel: MemoryPanelView = field(default_factory=MemoryPanelView)
    trade_plan: TradePlanView = field(default_factory=TradePlanView)
    position_status: PositionStatusView = field(default_factory=PositionStatusView)
    account_status: AccountStatusView = field(default_factory=AccountStatusView)
    last_signal: LastSignalView = field(default_factory=LastSignalView)
    system_panel: SystemPanelView = field(default_factory=SystemPanelView)
    events: Sequence[str] = ()
