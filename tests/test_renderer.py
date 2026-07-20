"""Tests for DashboardRenderer."""

from __future__ import annotations

from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    DashboardState,
    EngineStatus,
    LiveMarketView,
    MarketStatus,
    StatisticsView,
    SystemView,
)
from hotirjam_ai5.dashboard.renderer import DashboardRenderer


def test_render_includes_required_sections_and_title() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "HOTIRJAM AI 5" in text
    assert "SYSTEM" in text
    assert "LIVE MARKET" in text
    assert "STATISTICS" in text
    assert "LOG" in text
    assert "- Engine Status:" in text
    assert "- Connection Status:" in text
    assert "- Market Status:" in text
    assert "- Symbol:" in text
    assert "- Last Price:" in text
    assert "- Bid:" in text
    assert "- Ask:" in text
    assert "- Spread:" in text
    assert "- Volume:" in text
    assert "- Tick Count:" in text
    assert "- Tick Rate:" in text
    assert "- Running Time:" in text
    assert "- Last Events:" in text


def test_render_shows_placeholder_not_fake_prices() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "Last Price: —" in text
    assert "Bid: —" in text
    assert "Ask: —" in text
    assert "Spread: —" in text
    assert "Volume: —" in text
    assert "Tick Count: 0" in text


def test_render_with_real_market_values() -> None:
    state = DashboardState(
        system=SystemView(
            engine_status=EngineStatus.RUNNING,
            connection_status=ConnectionStatus.CONNECTED,
            market_status=MarketStatus.OPEN,
        ),
        market=LiveMarketView(
            symbol="MNQ",
            last_price=20100.5,
            bid=20100.25,
            ask=20100.5,
            volume=4.0,
        ),
        statistics=StatisticsView(
            tick_count=120,
            tick_rate=12.5,
            running_time_seconds=65,
        ),
        events=("tick accepted",),
    )
    text = DashboardRenderer().render(state)
    assert "Engine Status: RUNNING" in text
    assert "Connection Status: CONNECTED" in text
    assert "Market Status: OPEN" in text
    assert "Last Price: 20100.50" in text
    assert "Bid: 20100.25" in text
    assert "Ask: 20100.50" in text
    assert "Spread: 0.25" in text
    assert "Volume: 4" in text
    assert "Tick Count: 120" in text
    assert "Tick Rate: 12.50/s" in text
    assert "Running Time: 01:05" in text
    assert "• tick accepted" in text


def test_empty_log_shows_none() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "• (none)" in text
