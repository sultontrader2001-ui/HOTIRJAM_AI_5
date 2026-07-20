"""Pure string renderer for the terminal dashboard."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import DashboardState

SEPARATOR = "=" * 40
MISSING = "—"


def _format_price(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:.2f}"


def _format_volume(value: float | None) -> str:
    if value is None:
        return MISSING
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"


def _format_int(value: int | None) -> str:
    if value is None:
        return MISSING
    return str(value)


def _format_rate(value: float) -> str:
    return f"{value:.2f}/s"


def _format_ms(value: float | None) -> str:
    if value is None:
        return MISSING
    return f"{value:.0f} ms"


def _format_physics(value: float | None, *, digits: int = 4) -> str:
    if value is None:
        return MISSING
    return f"{value:.{digits}f}"


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_seconds(seconds: float) -> str:
    return f"{max(0, int(seconds))} s"


class DashboardRenderer:
    """Converts a DashboardState into the terminal layout."""

    def render(self, state: DashboardState) -> str:
        """Return the full dashboard text."""
        market = state.market
        stats = state.statistics
        health = state.feed_health
        dom = state.dom
        dom_health = state.dom_health
        physics = state.physics
        market_state = state.market_state
        transition = state.market_transition
        events = list(state.events) if state.events else ["(none)"]

        lines = [
            SEPARATOR,
            "HOTIRJAM AI 5",
            SEPARATOR,
            "SYSTEM",
            f"- Engine Status: {state.system.engine_status.value}",
            f"- Connection Status: {state.system.connection_status.value}",
            f"- Market Status: {state.system.market_status.value}",
            "LIVE MARKET",
            f"- Symbol: {market.symbol}",
            f"- Last Price: {_format_price(market.last_price)}",
            f"- Bid: {_format_price(market.bid)}",
            f"- Ask: {_format_price(market.ask)}",
            f"- Spread: {_format_price(market.spread)}",
            f"- Volume: {_format_volume(market.volume)}",
            "FEED HEALTH",
            f"- Feed Status: {health.feed_status.value}",
            f"- Connection Quality: {health.connection_quality.value}",
            f"- Last Tick Age: {_format_ms(health.last_tick_age_ms)}",
            f"- Tick Delay: {_format_ms(health.tick_delay_ms)}",
            f"- Average Tick Rate: {_format_rate(health.average_tick_rate)}",
            f"- Peak Tick Rate: {_format_rate(health.peak_tick_rate)}",
            "DOM",
            f"- Best Bid Size: {_format_int(dom.best_bid_size)}",
            f"- Best Ask Size: {_format_int(dom.best_ask_size)}",
            f"- Total Bid Size: {_format_int(dom.total_bid_size)}",
            f"- Total Ask Size: {_format_int(dom.total_ask_size)}",
            f"- Depth Levels: {_format_int(dom.depth_levels)}",
            f"- DOM Update Rate: {_format_rate(dom.update_rate)}",
            "DOM HEALTH",
            f"- Feed Status: {dom_health.feed_status.value}",
            f"- Connection Quality: {dom_health.connection_quality.value}",
            f"- Last Update Age: {_format_ms(dom_health.last_update_age_ms)}",
            f"- Update Rate: {_format_rate(dom_health.update_rate)}",
            f"- Peak Update Rate: {_format_rate(dom_health.peak_update_rate)}",
            "PHYSICS",
            f"- Spread: {_format_physics(physics.spread, digits=2)}",
            f"- Mid Price: {_format_physics(physics.mid_price, digits=2)}",
            f"- Tick Velocity: {_format_physics(physics.tick_velocity)}",
            f"- Tick Acceleration: {_format_physics(physics.tick_acceleration)}",
            "MARKET STATE",
            f"- State: {market_state.state}",
            f"- Reason: {market_state.reason}",
            "MARKET TRANSITION",
            f"- Current: {transition.current_state}",
            f"- Previous: {transition.previous_state}",
            f"- Transition: {transition.transition}",
            f"- Changed: {'YES' if transition.changed else 'NO'}",
            f"- Duration: {_format_seconds(transition.duration_seconds)}",
            "STATISTICS",
            f"- Tick Count: {stats.tick_count}",
            f"- Tick Rate: {_format_rate(stats.tick_rate)}",
            f"- Running Time: {_format_duration(stats.running_time_seconds)}",
            "LOG",
            "- Last Events:",
        ]
        for event in events:
            lines.append(f"  • {event}")
        return "\n".join(lines)
