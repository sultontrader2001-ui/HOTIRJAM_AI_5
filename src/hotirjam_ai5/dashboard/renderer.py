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


def _format_rate(value: float) -> str:
    return f"{value:.2f}/s"


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class DashboardRenderer:
    """Converts a DashboardState into the Sprint 1 terminal layout."""

    def render(self, state: DashboardState) -> str:
        """Return the full dashboard text."""
        market = state.market
        stats = state.statistics
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
