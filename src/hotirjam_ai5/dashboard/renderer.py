"""Pure string renderer for the terminal dashboard (Live Dashboard v2).

UI/UX only — no trading logic. Default layout is trading-focused; pass
``verbose=True`` (or ``--verbose``) for developer/pipeline details.
"""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import DashboardState, DecisionExplainabilityView

SEPARATOR = "═" * 60
SECTION = "─" * 60
MISSING = "—"
LABEL_WIDTH = 18


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


def _format_ms(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:.0f} ms"


def _format_physics(value: float | None, *, digits: int = 2) -> str:
    if value is None:
        return MISSING
    return f"{value:.{digits}f}"


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
    pad = max(0, (60 - len(banner)) // 2)
    centered = f"{' ' * pad}{banner}"
    return ["", centered, ""]


class DashboardRenderer:
    """Converts a DashboardState into the Live Dashboard v2 layout."""

    def __init__(self, *, verbose: bool = False) -> None:
        self._verbose = verbose

    @property
    def verbose(self) -> bool:
        return self._verbose

    def render(self, state: DashboardState) -> str:
        """Return the full dashboard text."""
        lines = [
            SEPARATOR,
            "HOTIRJAM AI 5 LIVE".center(60),
            SEPARATOR,
            "",
            *self._market_section(state),
            SECTION,
            *self._ai_status_section(state),
            SECTION,
            *self._trade_decision_section(state),
            SECTION,
            *self._performance_section(state),
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
            _row("NY Time", clock.new_york),
            _row("UZ Time", clock.tashkent),
            _row("Feed Health", state.feed_health.feed_status.value),
            _row("DOM Health", state.dom_health.feed_status.value),
        ]

    def _ai_status_section(self, state: DashboardState) -> list[str]:
        physics = state.physics
        liquidity = state.liquidity
        trade = state.trade_decision
        physics_text = (
            f"v={_format_physics(physics.tick_velocity)}  "
            f"a={_format_physics(physics.tick_acceleration)}"
        )
        liquidity_text = (
            f"{liquidity.shift} / {liquidity.imbalance}"
            if liquidity.shift != MISSING or liquidity.imbalance != MISSING
            else MISSING
        )
        readiness = (
            f"BUY {trade.decision_readiness} / SELL {trade.sell_decision_readiness}"
        )
        return [
            "AI STATUS",
            _row("Market State", state.market_state.state),
            _row("Behavior", state.market_behavior.behavior),
            _row("Physics", physics_text),
            _row("Liquidity", liquidity_text),
            _row("Assessment", state.decision_assessment.assessment_state),
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
            _row("BUY Score", f"{trade.buy_score} / 100"),
            _row("BUY Confidence", f"{trade.buy_confidence} %"),
            _row("SELL Score", f"{trade.sell_score} / 100"),
            _row("SELL Confidence", f"{trade.sell_confidence} %"),
            _row("Signal Stability", stability),
            _row("Memory Influence", f"{trade.memory_influence_pct:.1f}%"),
            _row("Memory Agreement", f"{trade.memory_agreement:.1f}"),
            _row("Memory Persistence", f"{trade.memory_persistence:.1f}"),
            *self._decision_explanation_section(trade.explainability),
        ]

    def _decision_explanation_section(
        self,
        expl: DecisionExplainabilityView,
    ) -> list[str]:
        """Render DECISION EXPLANATION from real snapshot evidence."""
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
            for line in expl.selection_lines:
                lines.append(line)
        if expl.checklist:
            lines.append("Missing")
            lines.extend(expl.checklist)
        return lines

    def _performance_section(self, state: DashboardState) -> list[str]:
        perf = state.performance
        return [
            "PERFORMANCE",
            _row("BUY Signals", _format_int(perf.buy_signals)),
            _row("SELL Signals", _format_int(perf.sell_signals)),
            _row("Win Rate", f"{perf.win_rate:.1f}%"),
            _row("Success", _format_int(perf.success_count)),
            _row("Failed", _format_int(perf.failed_count)),
            _row("Average Points", _format_physics(perf.average_points)),
            _row("Last Result", perf.last_result),
            _row("Last Signal", perf.last_signal_decision),
            _row("NY Time", perf.last_signal_new_york),
            _row("UZ Time", perf.last_signal_tashkent),
        ]

    def _system_section(self, state: DashboardState) -> list[str]:
        stats = state.statistics
        health = state.feed_health
        latency = health.tick_delay_ms
        if latency is None:
            latency = health.last_tick_age_ms
        return [
            "SYSTEM",
            _row("Tick Rate", _format_rate(stats.tick_rate)),
            _row("DOM Rate", _format_rate(state.dom_health.update_rate)),
            _row("Latency", _format_ms(latency)),
            _row("Runtime", _format_runtime(stats.running_time_seconds)),
            _row("Connection", state.system.connection_status.value),
        ]

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
            _row("BUY Readiness", trade.decision_readiness),
            _row("SELL Readiness", trade.sell_decision_readiness),
            "Explanation",
            _row("Assessment", trade.explanation.assessment),
            _row("Feed", trade.explanation.feed),
            _row("State", trade.explanation.market_state),
            _row("Behavior", trade.explanation.behavior),
            _row("Physics", trade.explanation.physics),
            _row("Liquidity", trade.explanation.liquidity),
            _row("Stability", trade.explanation.signal_stability),
            _row("Readiness", trade.explanation.readiness),
            "Summary",
            trade.explanation.summary,
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
