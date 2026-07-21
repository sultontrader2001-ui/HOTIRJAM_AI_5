"""Pure string renderer for the Professional Trading Dashboard v2.

Visualization only — no trading logic. Default layout is the live monitor;
pass ``verbose=True`` for developer/pipeline details.
"""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import (
    DashboardState,
    DecisionExplainabilityView,
    MemoryBandView,
    MemoryPanelView,
)

SEPARATOR = "═" * 64
SECTION = "─" * 64
MISSING = "--"
LABEL_WIDTH = 22


def _format_price(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:.2f}"


def _format_int(value: int | None) -> str:
    if value is None:
        return MISSING
    return str(value)


def _format_rate(value: float) -> str:
    if value == int(value):
        return f"{int(value)}/s"
    return f"{value:.2f}/s"


def _format_pct(value: float | None, *, digits: int = 1) -> str:
    if value is None:
        return MISSING
    return f"{value:.{digits}f}%"


def _format_points(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:.2f}"


def _format_signed_points(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:+.2f}"


def _format_physics(value: float | None, *, digits: int = 2) -> str:
    if value is None:
        return MISSING
    return f"{value:.{digits}f}"


def _format_ms(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:.1f} ms"


def _format_money(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return MISSING
    if signed:
        return f"${value:+,.2f}"
    return f"${value:,.2f}"


def _format_runtime(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _row(label: str, value: str) -> str:
    return f"{label:<{LABEL_WIDTH}}: {value}"


def _emphasize_decision(decision: str) -> list[str]:
    """Make the active decision the largest, easiest line to see."""
    if decision == "BUY_INTERNAL":
        banner = ">>>  BUY_INTERNAL  <<<"
    elif decision == "SELL_INTERNAL":
        banner = ">>>  SELL_INTERNAL  <<<"
    else:
        banner = f"Decision : {decision}"
    pad = max(0, (64 - len(banner)) // 2)
    centered = f"{' ' * pad}{banner}"
    return ["", centered, ""]


def _band_lines(title: str, band: MemoryBandView) -> list[str]:
    return [
        title,
        _row("Direction", band.direction or MISSING),
        _row("Strength", _format_pct(band.strength)),
        _row("Confidence", _format_pct(band.confidence)),
        _row("Persistence", _format_pct(band.persistence)),
    ]


class DashboardRenderer:
    """Converts a DashboardState into the Professional Trading Dashboard v2."""

    def __init__(self, *, verbose: bool = False) -> None:
        self._verbose = verbose

    @property
    def verbose(self) -> bool:
        return self._verbose

    def render(self, state: DashboardState) -> str:
        """Return the full dashboard text."""
        lines = [
            SEPARATOR,
            "HOTIRJAM AI 5 LIVE".center(64),
            SEPARATOR,
            "",
            *self._market_section(state),
            SECTION,
            *self._ai_status_section(state),
            SECTION,
            *self._trade_decision_section(state),
            SECTION,
            *self._memory_section(state.memory_panel),
            SECTION,
            *self._account_status_section(state),
            SECTION,
            *self._today_section(state),
            SECTION,
            *self._lifetime_section(state),
            SECTION,
            *self._signal_history_section(state),
            SECTION,
            *self._system_section(state),
        ]
        if self._verbose:
            lines.extend([SECTION, *self._verbose_section(state)])
        return "\n".join(lines)

    def _market_section(self, state: DashboardState) -> list[str]:
        market = state.market
        clock = state.display_clock
        return [
            "MARKET",
            _row("Symbol", market.symbol),
            _row("Price", _format_price(market.last_price)),
            _row("Bid", _format_price(market.bid)),
            _row("Ask", _format_price(market.ask)),
            _row("Spread", _format_price(market.spread)),
            _row("Market Status", state.system.market_status.value),
            _row("NY Time", clock.new_york if clock.new_york else MISSING),
            _row("UZ Time", clock.tashkent if clock.tashkent else MISSING),
            _row("Feed Health", state.feed_health.feed_status.value),
            _row("DOM Health", state.dom_health.feed_status.value),
            _row("Ticks/sec", _format_rate(state.statistics.tick_rate)),
            _row("DOM updates/sec", _format_rate(state.dom_health.update_rate)),
        ]

    def _ai_status_section(self, state: DashboardState) -> list[str]:
        physics = state.physics
        liquidity = state.liquidity
        trade = state.trade_decision
        physics_text = (
            f"v={_format_physics(physics.tick_velocity)}  "
            f"a={_format_physics(physics.tick_acceleration)}"
        )
        if liquidity.shift in (MISSING, "—") and liquidity.imbalance in (
            MISSING,
            "—",
        ):
            liquidity_text = MISSING
        else:
            shift = liquidity.shift if liquidity.shift not in ("—", "") else MISSING
            imb = (
                liquidity.imbalance
                if liquidity.imbalance not in ("—", "")
                else MISSING
            )
            liquidity_text = f"{shift} / {imb}"
        readiness = (
            f"BUY {trade.decision_readiness} / SELL {trade.sell_decision_readiness}"
        )
        return [
            "AI STATUS",
            _row("Market State", state.market_state.state),
            _row("Behavior", state.market_behavior.behavior),
            _row("Assessment", state.decision_assessment.assessment_state),
            _row("Physics", physics_text),
            _row("Liquidity", liquidity_text),
            _row("Decision Readiness", readiness),
        ]

    def _trade_decision_section(self, state: DashboardState) -> list[str]:
        trade = state.trade_decision
        stability = (
            f"BUY {trade.signal_stability} / SELL {trade.sell_signal_stability}"
        )
        return [
            "TRADE DECISION",
            *_emphasize_decision(trade.decision),
            _row("Decision", trade.decision),
            _row("BUY Score", f"{trade.buy_score} / 100"),
            _row("SELL Score", f"{trade.sell_score} / 100"),
            _row("BUY Confidence", f"{trade.buy_confidence} %"),
            _row("SELL Confidence", f"{trade.sell_confidence} %"),
            _row("Memory Influence %", _format_pct(trade.memory_influence_pct)),
            _row("Memory Agreement %", _format_pct(trade.memory_agreement)),
            _row("Memory Persistence %", _format_pct(trade.memory_persistence)),
            _row("Signal Stability", stability),
        ]

    def _memory_section(self, panel: MemoryPanelView) -> list[str]:
        lines = ["MEMORY"]
        lines.extend(_band_lines("Fast Band", panel.fast))
        lines.extend(_band_lines("Medium Band", panel.medium))
        lines.extend(_band_lines("Slow Band", panel.slow))
        lines.extend(
            [
                "Consensus",
                _row("Direction", panel.consensus_direction or MISSING),
                _row("Agreement", _format_pct(panel.consensus_agreement)),
                _row("Confidence", _format_pct(panel.consensus_confidence)),
                _row("Status", panel.consensus_status or MISSING),
            ]
        )
        return lines

    def _account_status_section(self, state: DashboardState) -> list[str]:
        acct = state.account_status
        return [
            "ACCOUNT STATUS",
            _row("Starting Balance", _format_money(acct.starting_balance)),
            _row("Current Balance", _format_money(acct.current_balance)),
            _row("Current Equity", _format_money(acct.current_equity)),
            _row("Today's P/L", _format_money(acct.today_pnl, signed=True)),
            _row("Lifetime P/L", _format_money(acct.lifetime_pnl, signed=True)),
            _row("Profit Target", _format_money(acct.profit_target)),
            _row("Progress %", _format_pct(acct.progress_pct)),
            _row("Remaining", _format_money(acct.remaining_profit)),
            _row("Risk Status", acct.risk_status or MISSING),
            _row("Win Rate", _format_pct(acct.win_rate)),
            _row("Profit Factor", _format_points(acct.profit_factor)),
        ]

    def _today_section(self, state: DashboardState) -> list[str]:
        today = state.today_stats
        return [
            "TODAY",
            _row("Signals Today", _format_int(today.signals)),
            _row("BUY Signals", _format_int(today.buy_signals)),
            _row("SELL Signals", _format_int(today.sell_signals)),
            _row("NO TRADE", _format_int(today.no_trade)),
            _row("Wins", _format_int(today.wins)),
            _row("Losses", _format_int(today.losses)),
            _row("Breakeven", _format_int(today.breakeven)),
            _row("Win Rate", _format_pct(today.win_rate)),
            _row("Average RR", _format_points(today.average_rr)),
            _row("Average Win", _format_signed_points(today.average_win)),
            _row(
                "Average Loss",
                _format_signed_points(
                    None if today.average_loss is None else -abs(today.average_loss)
                ),
            ),
            _row("Profit Factor", _format_points(today.profit_factor)),
            _row("Average MFE", _format_signed_points(today.average_mfe)),
            _row("Average MAE", _format_signed_points(today.average_mae)),
            _row("Memory Helped", _format_int(today.memory_helped)),
            _row("Memory Hurt", _format_int(today.memory_hurt)),
            _row("Memory No Effect", _format_int(today.memory_no_effect)),
        ]

    def _lifetime_section(self, state: DashboardState) -> list[str]:
        life = state.lifetime_stats
        return [
            "LIFETIME",
            _row("Total Signals", _format_int(life.signals)),
            _row("BUY Signals", _format_int(life.buy_signals)),
            _row("SELL Signals", _format_int(life.sell_signals)),
            _row("NO TRADE", _format_int(life.no_trade)),
            _row("Total Wins", _format_int(life.wins)),
            _row("Total Losses", _format_int(life.losses)),
            _row("Breakeven", _format_int(life.breakeven)),
            _row("Overall Win Rate", _format_pct(life.win_rate)),
            _row("Overall Profit Factor", _format_points(life.profit_factor)),
            _row("Average RR", _format_points(life.average_rr)),
            _row("Average Win", _format_signed_points(life.average_win)),
            _row(
                "Average Loss",
                _format_signed_points(
                    None if life.average_loss is None else -abs(life.average_loss)
                ),
            ),
            _row("Average MFE", _format_signed_points(life.average_mfe)),
            _row("Average MAE", _format_signed_points(life.average_mae)),
            _row("Largest Win", _format_signed_points(life.largest_win)),
            _row("Largest Loss", _format_signed_points(life.largest_loss)),
            _row("Net Points", _format_signed_points(life.net_points)),
            _row("Gross Profit", _format_signed_points(life.gross_profit)),
            _row(
                "Gross Loss",
                _format_signed_points(
                    None if life.gross_loss is None else -abs(life.gross_loss)
                ),
            ),
            _row("Avg Signals/Day", _format_points(life.average_signals_per_day)),
            _row("Avg Points/Signal", _format_signed_points(life.average_points_per_signal)),
            _row("Memory Helped", _format_int(life.memory_helped)),
            _row("Memory Hurt", _format_int(life.memory_hurt)),
            _row("Memory No Effect", _format_int(life.memory_no_effect)),
            _row("Memory Accuracy", _format_pct(life.memory_accuracy)),
        ]

    def _signal_history_section(self, state: DashboardState) -> list[str]:
        lines = ["SIGNAL HISTORY"]
        if not state.signal_history:
            lines.append(_row("Latest", MISSING))
            return lines
        # Compact table header
        lines.append(
            f"{'#':>2} {'Time':<8} {'Side':<4} {'Entry':>9} {'Exit':>9} "
            f"{'Result':<10} {'Pts':>7} {'Dur':<10} Memory"
        )
        for row in state.signal_history:
            entry = MISSING if row.entry is None else f"{row.entry:.2f}"
            exit_ = MISSING if row.exit is None else f"{row.exit:.2f}"
            pts = MISSING if row.points is None else f"{row.points:+.2f}"
            lines.append(
                f"{row.index:>2} {row.time_label:<8} {row.direction:<4} "
                f"{entry:>9} {exit_:>9} {row.result:<10} {pts:>7} "
                f"{row.duration_label:<10} {row.memory_effect}"
            )
        return lines

    def _system_section(self, state: DashboardState) -> list[str]:
        stats = state.statistics
        panel = state.system_panel
        return [
            "SYSTEM",
            _row("Runtime", _format_runtime(stats.running_time_seconds)),
            _row("Memory Records", _format_int(panel.memory_records)),
            _row("Decision Count", _format_int(panel.decision_count)),
            _row("Version", panel.version or MISSING),
            _row("Git Commit", panel.git_commit or MISSING),
        ]

    def _decision_explanation_section(
        self,
        expl: DecisionExplainabilityView,
    ) -> list[str]:
        """Verbose-only explainability block."""
        lines = [
            "DECISION EXPLANATION",
            expl.headline,
        ]
        if expl.buy_detail_lines:
            lines.extend(expl.buy_detail_lines)
        else:
            lines.append("BUY")
            if expl.buy_lines:
                lines.extend(expl.buy_lines)
            lines.append(f"{'TOTAL':<14} {expl.buy_total}")
            if expl.buy_reason:
                lines.append("Reason")
                lines.extend(expl.buy_reason.splitlines())

        if expl.sell_detail_lines:
            lines.extend(expl.sell_detail_lines)
        else:
            lines.append("SELL")
            if expl.sell_lines:
                lines.extend(expl.sell_lines)
            lines.append(f"{'TOTAL':<14} {expl.sell_total}")
            if expl.sell_reason:
                lines.append("Reason")
                lines.extend(expl.sell_reason.splitlines())

        if expl.selection_lines:
            lines.extend(expl.selection_lines)
        if expl.checklist:
            lines.append("Missing")
            lines.extend(expl.checklist)
        return lines

    def _verbose_section(self, state: DashboardState) -> list[str]:
        """Developer / pipeline details — hidden in default live mode."""
        foundation = state.decision_foundation
        intent = state.decision_intent
        evaluation = state.decision_evaluation
        assessment = state.decision_assessment
        trade = state.trade_decision
        transition = state.market_transition
        context = state.market_context
        events = list(state.events) if state.events else ["(none)"]
        foundation_detail = (
            foundation.summary
            if foundation.ready
            else (foundation.blocking_reason or foundation.summary)
        )
        lines = [
            "VERBOSE",
            "OBSERVATION LAYER",
            _row("Transition", transition.transition),
            _row("Context", context.summary),
            "DECISION FOUNDATION",
            _row("Ready", "YES" if foundation.ready else "NO"),
            foundation_detail,
            "DECISION INTENT",
            _row("Intent", intent.intent),
            _row("Reason", intent.reason),
            _row("Next", intent.next_step),
            "DECISION EVALUATION",
            _row("Status", evaluation.status),
            _row("Allowed", "YES" if evaluation.evaluation_allowed else "NO"),
            _row("Reason", evaluation.reason),
            _row("Next", evaluation.next_stage),
            "DECISION ASSESSMENT",
            _row("State", assessment.assessment_state),
            _row("Ready", "YES" if assessment.assessment_ready else "NO"),
            _row("Reason", assessment.reason),
            _row("Next", assessment.next_stage),
            "TRADE DECISION DETAIL",
            _row("Reason", trade.reason),
            _row("Next", trade.next_action),
            *self._decision_explanation_section(trade.explainability),
            "STATISTICS",
            _row("Tick Count", _format_int(state.statistics.tick_count)),
            _row(
                "BUY_INTERNAL",
                (
                    f"{state.statistics.buy_internal_count} "
                    f"({state.statistics.buy_internal_frequency:.1f}%)"
                ),
            ),
            _row(
                "SELL_INTERNAL",
                (
                    f"{state.statistics.sell_internal_count} "
                    f"({state.statistics.sell_internal_frequency:.1f}%)"
                ),
            ),
            _row(
                "NO_TRADE",
                (
                    f"{state.statistics.no_trade_count} "
                    f"({state.statistics.no_trade_frequency:.1f}%)"
                ),
            ),
            "LOG",
        ]
        for event in events:
            lines.append(f"• {event}")
        return lines
