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
            *self._performance_section(state),
            SECTION,
            *self._last_signal_section(state),
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

    def _performance_section(self, state: DashboardState) -> list[str]:
        perf = state.performance
        return [
            "PERFORMANCE",
            _row("Signals Today", _format_int(perf.signals_today)),
            _row("BUY Signals", _format_int(perf.buy_signals)),
            _row("SELL Signals", _format_int(perf.sell_signals)),
            _row("Winning Signals", _format_int(perf.success_count)),
            _row("Losing Signals", _format_int(perf.failed_count)),
            _row("Win Rate", _format_pct(perf.win_rate)),
            _row("Average MFE", _format_signed_points(perf.average_mfe)),
            _row("Average MAE", _format_signed_points(perf.average_mae)),
            _row("Average RR", _format_points(perf.average_rr)),
            _row("Profit Factor", _format_points(perf.profit_factor)),
            _row("Decision Accuracy", _format_pct(perf.decision_accuracy)),
        ]

    def _last_signal_section(self, state: DashboardState) -> list[str]:
        last = state.last_signal
        return [
            "LAST SIGNAL",
            _row("Direction", last.direction or MISSING),
            _row("Entry Time", last.entry_time or MISSING),
            _row("Exit Time", last.exit_time or MISSING),
            _row("Duration", last.duration or MISSING),
            _row("Result", last.result or MISSING),
            _row("Points", _format_signed_points(last.points)),
            _row("Memory", last.memory_effect or MISSING),
        ]

    def _system_section(self, state: DashboardState) -> list[str]:
        stats = state.statistics
        panel = state.system_panel
        return [
            "SYSTEM",
            _row("Runtime", _format_runtime(stats.running_time_seconds)),
            _row("Memory Records", _format_int(panel.memory_records)),
            _row("Memory Usage", _format_pct(panel.memory_usage_pct)),
            _row("Decision Count", _format_int(panel.decision_count)),
            _row(
                "Append Rate",
                (
                    MISSING
                    if panel.append_rate is None
                    else f"{panel.append_rate:.2f}/s"
                ),
            ),
            _row("Average Decision Time", _format_ms(panel.average_decision_ms)),
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
