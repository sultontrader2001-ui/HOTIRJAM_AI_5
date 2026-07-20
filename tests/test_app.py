"""Tests for DashboardController and DashboardApp."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from hotirjam_ai5.dashboard.app import DashboardApp, build_arg_parser, main
from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    EngineStatus,
    MarketStatus,
)
from hotirjam_ai5.dashboard.renderer import DashboardRenderer
from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.live_data.ingress import LiveTickIngress


def test_controller_start_sets_connecting_and_logs() -> None:
    controller = DashboardController()
    controller.start()
    state = controller.snapshot()
    assert state.system.engine_status is EngineStatus.RUNNING
    assert state.system.connection_status is ConnectionStatus.CONNECTING
    assert state.system.market_status is MarketStatus.WAITING
    assert state.market.last_price is None
    assert "Dashboard started" in state.events
    assert any("waiting for first live tick" in event for event in state.events)


def test_controller_stop_sets_stopped() -> None:
    controller = DashboardController()
    controller.start()
    controller.stop()
    assert controller.snapshot().system.engine_status is EngineStatus.STOPPED


def test_app_runs_limited_frames_without_fake_market_data() -> None:
    buffer = io.StringIO()
    sleeps: list[float] = []
    app = DashboardApp(
        controller=DashboardController(symbol="MNQ"),
        renderer=DashboardRenderer(),
        display=TerminalDisplay(stream=buffer),
        refresh_seconds=0.01,
        sleep_fn=sleeps.append,
    )
    code = app.run(max_frames=2)
    assert code == 0
    output = buffer.getvalue()
    assert output.count("HOTIRJAM AI 5") == 2
    assert "Last Price: —" in output
    assert "Connection Status: CONNECTING" in output
    assert len(sleeps) == 1


def test_app_updates_from_live_ingress(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text("", encoding="utf-8")
    ingress = LiveTickIngress(path)
    # Prime tail at EOF (no replay).
    assert ingress.poll() == ()

    line = json.dumps(
        {
            "timestamp": 1_700_000_000.0,
            "symbol": "MNQ",
            "last_price": 20110.0,
            "bid": 20109.75,
            "ask": 20110.0,
            "volume": 5.0,
        }
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")

    buffer = io.StringIO()
    app = DashboardApp(
        controller=DashboardController(symbol="MNQ"),
        ingress=ingress,
        renderer=DashboardRenderer(),
        display=TerminalDisplay(stream=buffer),
        refresh_seconds=0.01,
        sleep_fn=lambda _: None,
    )
    code = app.run(max_frames=1)
    assert code == 0
    output = buffer.getvalue()
    assert "Connection Status: CONNECTED" in output
    assert "Last Price: 20110.00" in output
    assert "Bid: 20109.75" in output
    assert "Ask: 20110.00" in output
    assert "Volume: 5" in output
    assert "Tick Count: 1" in output
    assert "Connection established" in output
    assert "Tick received" in output


def test_app_rejects_non_positive_refresh() -> None:
    with pytest.raises(ValueError, match="refresh_seconds"):
        DashboardApp(refresh_seconds=0)


def test_cli_parser_defaults() -> None:
    args = build_arg_parser().parse_args([])
    assert args.symbol == "MNQ"
    assert args.refresh == 0.25
    assert args.tick_file is None
    assert args.stale_seconds == 5.0


def test_main_runs_one_frame_via_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int | None] = []

    class StubApp:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def run(self, *, max_frames: int | None = None) -> int:
            calls.append(max_frames)
            return 0

    monkeypatch.setattr("hotirjam_ai5.dashboard.app.DashboardApp", StubApp)
    code = main(["--refresh", "0.5", "--symbol", "MNQ"])
    assert code == 0
    assert calls == [None]
