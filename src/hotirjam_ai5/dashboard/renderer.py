"""Pure string renderer for the terminal dashboard."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import DashboardState

SEPARATOR = "═" * 62
MISSING = "—"
LEFT_WIDTH = 26


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


def _title_case_status(value: str) -> str:
    return value[:1].upper() + value[1:].lower() if value else MISSING


def _pair(left: str, right: str = "") -> str:
    return f"{left:<{LEFT_WIDTH}}{right}".rstrip()


def _zip_columns(left_rows: list[str], right_rows: list[str]) -> list[str]:
    height = max(len(left_rows), len(right_rows))
    lines: list[str] = []
    for index in range(height):
        left = left_rows[index] if index < len(left_rows) else ""
        right = right_rows[index] if index < len(right_rows) else ""
        lines.append(_pair(left, right))
    return lines


class DashboardRenderer:
    """Converts a DashboardState into the compact terminal layout."""

    def render(self, state: DashboardState) -> str:
        """Return the full dashboard text."""
        market = state.market
        stats = state.statistics
        health = state.feed_health
        dom_health = state.dom_health
        physics = state.physics
        market_state = state.market_state
        transition = state.market_transition
        behavior = state.market_behavior
        context = state.market_context
        foundation = state.decision_foundation
        intent = state.decision_intent
        evaluation = state.decision_evaluation
        assessment = state.decision_assessment
        trade = state.trade_decision
        events = list(state.events) if state.events else ["(none)"]

        system_rows = [
            "SYSTEM",
            f"Status : {state.system.engine_status.value}",
            f"Conn   : {state.system.connection_status.value}",
            f"Market : {state.system.market_status.value}",
        ]
        market_rows = [
            "LIVE MARKET",
            f"Symbol : {market.symbol}",
            f"Price  : {_format_price(market.last_price)}",
            f"Bid    : {_format_price(market.bid)}",
            f"Ask    : {_format_price(market.ask)}",
            f"Spread : {_format_price(market.spread)}",
        ]
        feed_rows = [
            "FEED HEALTH",
            _title_case_status(health.feed_status.value),
            f"Quality : {health.connection_quality.value}",
            f"TickAge : {_format_ms(health.last_tick_age_ms)}",
            f"Rate    : {_format_rate(health.average_tick_rate)}",
        ]
        dom_rows = [
            "DOM HEALTH",
            _title_case_status(dom_health.feed_status.value),
            f"Quality : {dom_health.connection_quality.value}",
            f"DOMAge  : {_format_ms(dom_health.last_update_age_ms)}",
            f"Rate    : {_format_rate(dom_health.update_rate)}",
        ]
        physics_rows = [
            "PHYSICS",
            f"Velocity : {_format_physics(physics.tick_velocity)}",
            f"Accel    : {_format_physics(physics.tick_acceleration)}",
            f"Spread   : {_format_physics(physics.spread, digits=2)}",
        ]
        stats_rows = [
            "STATISTICS",
            f"Tick Rate : {_format_rate(stats.tick_rate)}",
            f"Tick Count: {_format_int(stats.tick_count)}",
        ]

        foundation_detail = (
            foundation.summary
            if foundation.ready
            else (foundation.blocking_reason or foundation.summary)
        )

        lines = [
            "HOTIRJAM AI 5",
            SEPARATOR,
            *_zip_columns(system_rows, market_rows),
            *_zip_columns(feed_rows, dom_rows),
            *_zip_columns(physics_rows, stats_rows),
            "MARKET ANALYSIS",
            f"State       : {market_state.state}",
            f"Transition  : {transition.transition}",
            f"Behavior    : {behavior.behavior}",
            "CONTEXT",
            context.summary,
            "DECISION FOUNDATION",
            f"Ready : {'YES' if foundation.ready else 'NO'}",
            foundation_detail,
            "DECISION INTENT",
            f"Intent : {intent.intent}",
            f"Reason : {intent.reason}",
            f"Next   : {intent.next_step}",
            "DECISION EVALUATION",
            f"Status  : {evaluation.status}",
            f"Allowed : {'YES' if evaluation.evaluation_allowed else 'NO'}",
            f"Reason  : {evaluation.reason}",
            f"Next    : {evaluation.next_stage}",
            "DECISION ASSESSMENT",
            f"State : {assessment.assessment_state}",
            f"Ready : {'YES' if assessment.assessment_ready else 'NO'}",
            f"Reason: {assessment.reason}",
            f"Next  : {assessment.next_stage}",
            "TRADE DECISION",
            f"Decision: {trade.decision}",
            f"Reason  : {trade.reason}",
            f"Next    : {trade.next_action}",
            "LOG",
        ]
        for event in events:
            lines.append(f"• {event}")
        return "\n".join(lines)
