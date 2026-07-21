"""Professional dual-column LIVE dashboard renderer (Sprint 48).

Layout only — no trading logic. Width ≥160 → two columns; otherwise single column.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence

from hotirjam_ai5.dashboard.models import (
    DashboardState,
    DecisionExplainabilityView,
    MemoryBandView,
    MemoryPanelView,
)

MISSING = "--"
LABEL_WIDTH = 18
DUAL_COLUMN_MIN_WIDTH = 160
DEFAULT_WIDTH = 80
DUAL_HISTORY_ROWS = 8
SINGLE_HISTORY_ROWS = 12

# Box-drawing characters
_H = "─"
_V = "│"
_TL = "┌"
_TR = "┐"
_BL = "└"
_BR = "┘"
_DH = "═"
_DV = "║"
_DTL = "╔"
_DTR = "╗"
_DBL = "╚"
_DBR = "╝"


def detect_terminal_width() -> int:
    """Return current terminal columns (minimum 40)."""
    try:
        return max(40, shutil.get_terminal_size(fallback=(DEFAULT_WIDTH, 24)).columns)
    except OSError:
        return DEFAULT_WIDTH


def _format_price(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:.2f}"


def _format_int(value: int | None) -> str:
    if value is None:
        return MISSING
    return str(value)


def _format_rate(value: float | None) -> str:
    if value is None:
        return MISSING
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


def _pad(text: str, width: int) -> str:
    """Pad or leave as-is — never clip content (widen visually via pad only)."""
    if len(text) >= width:
        return text
    return text.ljust(width)


def _center(text: str, width: int) -> str:
    if len(text) >= width:
        return text
    pad = width - len(text)
    left = pad // 2
    return (" " * left) + text + (" " * (pad - left))


def _kv(label: str, value: str, width: int) -> str:
    """Label left, value right-aligned within ``width`` (no clipping)."""
    lab = label if len(label) <= LABEL_WIDTH else label[:LABEL_WIDTH]
    lab = f"{lab:<{LABEL_WIDTH}}"
    # Reserve at least 1 space between label and value.
    avail = max(1, width - LABEL_WIDTH - 1)
    val = value
    if len(val) > avail:
        # Prefer showing full value (no clip); overflow is allowed per acceptance.
        return f"{lab} {val}"
    return f"{lab} {val:>{avail}}"


def _framed_top(title: str, width: int) -> str:
    """Top border with centered title carved into the line."""
    label = f" {title} "
    if len(label) >= width:
        return f"{_TL}{_H * width}{_TR}"
    side = width - len(label)
    left = side // 2
    right = side - left
    return f"{_TL}{_H * left}{label}{_H * right}{_TR}"


def _framed_bottom(width: int) -> str:
    return f"{_BL}{_H * width}{_BR}"


def _framed_row(content: str, width: int) -> str:
    body = _pad(content, width)
    if len(body) > width:
        return f"{_V}{body}{_V}"
    return f"{_V}{body}{_V}"


def _panel(title: str, rows: Sequence[tuple[str, str]], width: int) -> list[str]:
    """Boxed panel: title header + key/value rows."""
    inner = max(24, width - 2)
    lines = [_framed_top(title, inner)]
    for label, value in rows:
        lines.append(_framed_row(_kv(label, value, inner), inner))
    lines.append(_framed_bottom(inner))
    return lines


def _panel_lines(title: str, body_lines: Sequence[str], width: int) -> list[str]:
    """Boxed panel with free-form body lines (already width-sized content)."""
    inner = max(24, width - 2)
    lines = [_framed_top(title, inner)]
    for raw in body_lines:
        lines.append(_framed_row(_pad(raw, inner), inner))
    lines.append(_framed_bottom(inner))
    return lines


def _stack_panels(panels: Sequence[list[str]]) -> list[str]:
    out: list[str] = []
    for panel in panels:
        if out:
            out.append("")  # small gap between panels
        out.extend(panel)
    return out


def _merge_columns(left: list[str], right: list[str], *, gap: str = " ") -> list[str]:
    height = max(len(left), len(right))
    left_w = max((len(x) for x in left), default=0)
    right_w = max((len(x) for x in right), default=0)
    left_p = [_pad(x, left_w) for x in left] + [" " * left_w] * (height - len(left))
    right_p = [_pad(x, right_w) for x in right] + [" " * right_w] * (height - len(right))
    return [f"{L}{gap}{R}" for L, R in zip(left_p, right_p, strict=True)]


class DashboardRenderer:
    """Converts a DashboardState into the Professional Trading Dashboard."""

    def __init__(
        self,
        *,
        verbose: bool = False,
        width: int | None = None,
    ) -> None:
        self._verbose = verbose
        self._fixed_width = width

    @property
    def verbose(self) -> bool:
        return self._verbose

    @property
    def fixed_width(self) -> int | None:
        """Optional width override (tests / forced layout)."""
        return self._fixed_width

    def render(self, state: DashboardState, *, width: int | None = None) -> str:
        """Return the full dashboard text for the given terminal width."""
        cols = width if width is not None else self._fixed_width
        if cols is None:
            cols = detect_terminal_width()
        if cols >= DUAL_COLUMN_MIN_WIDTH:
            body = self._render_dual(state, cols)
        else:
            body = self._render_single(state, max(cols, 64))
        if self._verbose:
            verbose_w = cols if cols >= DUAL_COLUMN_MIN_WIDTH else max(cols, 64)
            body = body + "\n" + "\n".join(self._verbose_section(state, verbose_w))
        return body

    def _render_dual(self, state: DashboardState, cols: int) -> str:
        gap = 1
        col_w = (cols - gap) // 2
        left = _stack_panels(
            [
                self._market_panel(state, col_w),
                self._ai_status_panel(state, col_w),
                self._trade_decision_panel(state, col_w),
                self._trade_plan_panel(state, col_w),
                self._position_status_panel(state, col_w),
                self._memory_panel(state.memory_panel, col_w),
            ]
        )
        right = _stack_panels(
            [
                self._today_panel(state, col_w),
                self._lifetime_panel(state, col_w),
                self._account_status_panel(state, col_w),
                self._system_panel(state, col_w),
            ]
        )
        merged = _merge_columns(left, right, gap=" " * gap)
        banner = self._banner(cols)
        history = self._signal_history_panel(state, cols, limit=DUAL_HISTORY_ROWS)
        return "\n".join([*banner, *merged, "", *history])

    def _render_single(self, state: DashboardState, cols: int) -> str:
        panels = _stack_panels(
            [
                self._market_panel(state, cols),
                self._ai_status_panel(state, cols),
                self._trade_decision_panel(state, cols),
                self._trade_plan_panel(state, cols),
                self._position_status_panel(state, cols),
                self._memory_panel(state.memory_panel, cols),
                self._today_panel(state, cols),
                self._lifetime_panel(state, cols),
                self._account_status_panel(state, cols),
                self._system_panel(state, cols),
                self._signal_history_panel(state, cols, limit=SINGLE_HISTORY_ROWS),
            ]
        )
        return "\n".join([*self._banner(cols), *panels])

    def _banner(self, cols: int) -> list[str]:
        inner = max(24, cols - 2)
        title = _center("HOTIRJAM AI 5 LIVE", inner)
        return [
            f"{_DTL}{_DH * inner}{_DTR}",
            f"{_DV}{title}{_DV}",
            f"{_DBL}{_DH * inner}{_DBR}",
            "",
        ]

    def _market_panel(self, state: DashboardState, width: int) -> list[str]:
        market = state.market
        clock = state.display_clock
        return _panel(
            "MARKET",
            [
                ("Symbol", market.symbol or MISSING),
                ("Price", _format_price(market.last_price)),
                ("Bid", _format_price(market.bid)),
                ("Ask", _format_price(market.ask)),
                ("Spread", _format_price(market.spread)),
                ("Market Status", state.system.market_status.value),
                ("NY Time", clock.new_york if clock.new_york else MISSING),
                ("UZ Time", clock.tashkent if clock.tashkent else MISSING),
                ("Feed Health", state.feed_health.feed_status.value),
                ("DOM Health", state.dom_health.feed_status.value),
                ("Ticks/sec", _format_rate(state.statistics.tick_rate)),
                ("DOM updates/sec", _format_rate(state.dom_health.update_rate)),
            ],
            width,
        )

    def _ai_status_panel(self, state: DashboardState, width: int) -> list[str]:
        physics = state.physics
        liquidity = state.liquidity
        trade = state.trade_decision
        physics_text = (
            f"v={_format_physics(physics.tick_velocity)}  "
            f"a={_format_physics(physics.tick_acceleration)}"
        )
        if liquidity.shift in (MISSING, "—", "") and liquidity.imbalance in (
            MISSING,
            "—",
            "",
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
        return _panel(
            "AI STATUS",
            [
                ("Market State", state.market_state.state),
                ("Behavior", state.market_behavior.behavior),
                ("Assessment", state.decision_assessment.assessment_state),
                ("Physics", physics_text),
                ("Liquidity", liquidity_text),
                ("Decision Readiness", readiness),
            ],
            width,
        )

    def _trade_decision_panel(self, state: DashboardState, width: int) -> list[str]:
        trade = state.trade_decision
        stability = (
            f"BUY {trade.signal_stability} / SELL {trade.sell_signal_stability}"
        )
        decision = trade.decision
        if decision == "BUY_INTERNAL":
            decision_disp = ">>> BUY_INTERNAL <<<"
        elif decision == "SELL_INTERNAL":
            decision_disp = ">>> SELL_INTERNAL <<<"
        else:
            decision_disp = decision
        return _panel(
            "TRADE DECISION",
            [
                ("Decision", decision_disp),
                ("BUY Score", f"{trade.buy_score} / 100"),
                ("SELL Score", f"{trade.sell_score} / 100"),
                ("BUY Confidence", f"{trade.buy_confidence} %"),
                ("SELL Confidence", f"{trade.sell_confidence} %"),
                ("Memory Influence %", _format_pct(trade.memory_influence_pct)),
                ("Memory Agreement %", _format_pct(trade.memory_agreement)),
                ("Memory Persistence %", _format_pct(trade.memory_persistence)),
                ("Signal Stability", stability),
            ],
            width,
        )

    def _trade_plan_panel(self, state: DashboardState, width: int) -> list[str]:
        plan = state.trade_plan
        return _panel(
            "TRADE PLAN",
            [
                ("Direction", plan.direction or MISSING),
                ("Entry", _format_price(plan.entry)),
                ("Stop Loss", _format_price(plan.stop_loss)),
                ("Take Profit", _format_price(plan.take_profit)),
                ("Risk", _format_points(plan.risk)),
                ("Reward", _format_points(plan.reward)),
                ("RR", _format_points(plan.risk_reward)),
                ("Trade Status", plan.status or MISSING),
            ],
            width,
        )

    def _position_status_panel(self, state: DashboardState, width: int) -> list[str]:
        pos = state.position_status
        return _panel(
            "POSITION STATUS",
            [
                ("Status", pos.status or MISSING),
                ("Current Trade", pos.current_trade_id or MISSING),
                ("Entry", _format_price(pos.entry)),
                ("Current P/L", _format_signed_points(pos.current_pnl)),
                ("Duration", pos.duration or MISSING),
                ("Distance to SL", _format_signed_points(pos.distance_to_sl)),
                ("Distance to TP", _format_signed_points(pos.distance_to_tp)),
                ("New Signals", pos.new_signals or MISSING),
                ("Blocked Signals", _format_int(pos.blocked_signals)),
                ("Blocked BUY", _format_int(pos.blocked_buy)),
                ("Blocked SELL", _format_int(pos.blocked_sell)),
                ("Avg Active Duration", pos.average_active_duration or MISSING),
            ],
            width,
        )

    def _memory_panel(self, panel: MemoryPanelView, width: int) -> list[str]:
        def band_value(band: MemoryBandView) -> str:
            return (
                f"{band.direction or MISSING}  "
                f"S:{_format_pct(band.strength)}  "
                f"C:{_format_pct(band.confidence)}  "
                f"P:{_format_pct(band.persistence)}"
            )

        return _panel(
            "MEMORY",
            [
                ("Fast Band", band_value(panel.fast)),
                ("Medium Band", band_value(panel.medium)),
                ("Slow Band", band_value(panel.slow)),
                ("Consensus Dir", panel.consensus_direction or MISSING),
                ("Agreement", _format_pct(panel.consensus_agreement)),
                ("Confidence", _format_pct(panel.consensus_confidence)),
                ("Status", panel.consensus_status or MISSING),
            ],
            width,
        )

    def _today_panel(self, state: DashboardState, width: int) -> list[str]:
        today = state.today_stats
        return _panel(
            "TODAY",
            [
                ("Signals", _format_int(today.signals)),
                ("BUY", _format_int(today.buy_signals)),
                ("SELL", _format_int(today.sell_signals)),
                ("Wins", _format_int(today.wins)),
                ("Losses", _format_int(today.losses)),
                ("Win Rate", _format_pct(today.win_rate)),
                ("Profit Factor", _format_points(today.profit_factor)),
                ("Average RR", _format_points(today.average_rr)),
                ("Average MFE", _format_signed_points(today.average_mfe)),
                ("Average MAE", _format_signed_points(today.average_mae)),
            ],
            width,
        )

    def _lifetime_panel(self, state: DashboardState, width: int) -> list[str]:
        life = state.lifetime_stats
        return _panel(
            "LIFETIME",
            [
                ("Total Signals", _format_int(life.signals)),
                ("Wins", _format_int(life.wins)),
                ("Losses", _format_int(life.losses)),
                ("Overall Win Rate", _format_pct(life.win_rate)),
                ("Overall Profit Factor", _format_points(life.profit_factor)),
                ("Memory Accuracy", _format_pct(life.memory_accuracy)),
                ("Net Profit", _format_signed_points(life.net_points)),
                ("Largest Win", _format_signed_points(life.largest_win)),
                ("Largest Loss", _format_signed_points(life.largest_loss)),
            ],
            width,
        )

    def _account_status_panel(self, state: DashboardState, width: int) -> list[str]:
        acct = state.account_status
        return _panel(
            "ACCOUNT STATUS",
            [
                ("Starting Balance", _format_money(acct.starting_balance)),
                ("Current Balance", _format_money(acct.current_balance)),
                ("Current Equity", _format_money(acct.current_equity)),
                ("Today's P/L", _format_money(acct.today_pnl, signed=True)),
                ("Weekly P/L", _format_money(acct.weekly_pnl, signed=True)),
                ("Monthly P/L", _format_money(acct.monthly_pnl, signed=True)),
                ("Lifetime P/L", _format_money(acct.lifetime_pnl, signed=True)),
                ("Profit Target", _format_money(acct.profit_target)),
                ("Progress", _format_pct(acct.progress_pct)),
                ("Remaining", _format_money(acct.remaining_profit)),
                ("Risk Status", acct.risk_status or MISSING),
                ("Win Rate", _format_pct(acct.win_rate)),
                ("Profit Factor", _format_points(acct.profit_factor)),
            ],
            width,
        )

    def _system_panel(self, state: DashboardState, width: int) -> list[str]:
        stats = state.statistics
        panel = state.system_panel
        append = (
            MISSING
            if panel.append_rate is None
            else f"{panel.append_rate:.2f}/s"
        )
        return _panel(
            "SYSTEM",
            [
                ("Runtime", _format_runtime(stats.running_time_seconds)),
                ("Decision Count", _format_int(panel.decision_count)),
                ("Memory Records", _format_int(panel.memory_records)),
                ("Memory Usage", _format_pct(panel.memory_usage_pct)),
                ("Append Rate", append),
                ("Version", panel.version or MISSING),
                ("Git Commit", panel.git_commit or MISSING),
            ],
            width,
        )

    def _signal_history_panel(
        self,
        state: DashboardState,
        width: int,
        *,
        limit: int,
    ) -> list[str]:
        inner = max(40, width - 2)
        header = (
            f"{'#':>2}  {'Time':<8}  {'Side':<4}  {'Result':<4}  "
            f"{'Points':>7}  {'Duration':<10}  Memory"
        )
        body: list[str] = [_pad(header, inner)]
        rows = state.signal_history[:limit]
        if not rows:
            body.append(_pad(f"  {MISSING}", inner))
        else:
            for row in rows:
                result = row.result
                if result == "BREAKEVEN":
                    result = "BE"
                elif result == "WIN":
                    result = "WIN"
                elif result == "LOSS":
                    result = "LOSS"
                pts = MISSING if row.points is None else f"{row.points:.2f}"
                line = (
                    f"{row.index:>2}  {row.time_label:<8}  {row.direction:<4}  "
                    f"{result:<4}  {pts:>7}  {row.duration_label:<10}  "
                    f"{row.memory_effect}"
                )
                body.append(_pad(line, inner))
        return _panel_lines("SIGNAL HISTORY", body, width)

    def _verbose_section(self, state: DashboardState, width: int) -> list[str]:
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
        rows: list[tuple[str, str]] = [
            ("Transition", transition.transition),
            ("Context", context.summary),
            ("Foundation Ready", "YES" if foundation.ready else "NO"),
            ("Foundation", foundation_detail),
            ("Intent", intent.intent),
            ("Intent Reason", intent.reason),
            ("Intent Next", intent.next_step),
            ("Eval Status", evaluation.status),
            ("Eval Allowed", "YES" if evaluation.evaluation_allowed else "NO"),
            ("Eval Reason", evaluation.reason),
            ("Assessment", assessment.assessment_state),
            ("Assess Ready", "YES" if assessment.assessment_ready else "NO"),
            ("Trade Reason", trade.reason),
            ("Trade Next", trade.next_action),
            ("Tick Count", _format_int(state.statistics.tick_count)),
            (
                "BUY_INTERNAL",
                (
                    f"{state.statistics.buy_internal_count} "
                    f"({state.statistics.buy_internal_frequency:.1f}%)"
                ),
            ),
            (
                "SELL_INTERNAL",
                (
                    f"{state.statistics.sell_internal_count} "
                    f"({state.statistics.sell_internal_frequency:.1f}%)"
                ),
            ),
            (
                "NO_TRADE",
                (
                    f"{state.statistics.no_trade_count} "
                    f"({state.statistics.no_trade_frequency:.1f}%)"
                ),
            ),
        ]
        lines = _panel("VERBOSE", rows, width)
        lines.extend(self._decision_explanation_section(trade.explainability, width))
        log_lines = [f"• {event}" for event in events]
        lines.extend(_panel_lines("LOG", log_lines, width))
        return lines

    def _decision_explanation_section(
        self,
        expl: DecisionExplainabilityView,
        width: int,
    ) -> list[str]:
        body: list[str] = [expl.headline or MISSING]
        if expl.buy_detail_lines:
            body.extend(expl.buy_detail_lines)
        else:
            body.append("BUY")
            body.extend(expl.buy_lines)
            body.append(f"TOTAL {expl.buy_total}")
            if expl.buy_reason:
                body.extend(expl.buy_reason.splitlines())
        if expl.sell_detail_lines:
            body.extend(expl.sell_detail_lines)
        else:
            body.append("SELL")
            body.extend(expl.sell_lines)
            body.append(f"TOTAL {expl.sell_total}")
            if expl.sell_reason:
                body.extend(expl.sell_reason.splitlines())
        body.extend(expl.selection_lines)
        if expl.checklist:
            body.append("Missing")
            body.extend(expl.checklist)
        return _panel_lines("DECISION EXPLANATION", body, width)
