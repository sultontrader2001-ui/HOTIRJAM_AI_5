"""Tests for DashboardController and DashboardApp."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from hotirjam_ai5.dashboard.app import (
    DashboardApp,
    build_arg_parser,
    clamp_refresh_seconds,
    main,
)
from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.dashboard.models import (
    ConnectionStatus,
    EngineStatus,
    MarketStatus,
)
from hotirjam_ai5.dashboard.renderer import DashboardRenderer
from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.live_data.ingress import LiveTickIngress


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_controller_start_sets_connecting_without_noise_logs() -> None:
    controller = DashboardController()
    controller.start()
    state = controller.snapshot()
    assert state.system.engine_status is EngineStatus.RUNNING
    assert state.system.connection_status is ConnectionStatus.CONNECTING
    assert state.system.market_status is MarketStatus.WAITING
    assert state.market.last_price is None
    assert state.events == ()


def test_controller_stop_sets_stopped() -> None:
    controller = DashboardController()
    controller.start()
    controller.stop()
    assert controller.snapshot().system.engine_status is EngineStatus.STOPPED


def test_clamp_refresh_seconds_bounds() -> None:
    assert clamp_refresh_seconds(0.25) == 0.25
    assert clamp_refresh_seconds(0.5) == 0.5
    assert clamp_refresh_seconds(0.1) == 0.25
    assert clamp_refresh_seconds(2.0) == 0.5
    with pytest.raises(ValueError, match="refresh_seconds"):
        clamp_refresh_seconds(0)


def test_app_polls_faster_than_display_refresh() -> None:
    clock = FakeClock(0.0)
    sleeps: list[float] = []
    poll_calls = {"n": 0}

    class CountingApp(DashboardApp):
        def poll_once(self) -> None:
            poll_calls["n"] += 1
            super().poll_once()

    def sleep_fn(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    app = CountingApp(
        controller=DashboardController(symbol="MNQ"),
        renderer=DashboardRenderer(),
        display=TerminalDisplay(stream=io.StringIO()),
        refresh_seconds=0.25,
        poll_seconds=0.05,
        sleep_fn=sleep_fn,
        clock=clock,
    )
    code = app.run(max_frames=2)
    assert code == 0
    # Two display frames require multiple poll cycles at 50ms inside 250ms budget.
    assert poll_calls["n"] >= 2
    assert all(sleep == 0.05 for sleep in sleeps)
    assert app.refresh_seconds == 0.25
    assert app.poll_seconds == 0.05


def test_app_runs_limited_frames_without_fake_market_data() -> None:
    buffer = io.StringIO()
    clock = FakeClock(0.0)
    app = DashboardApp(
        controller=DashboardController(symbol="MNQ"),
        renderer=DashboardRenderer(width=100),
        display=TerminalDisplay(stream=buffer),
        refresh_seconds=0.25,
        poll_seconds=0.05,
        sleep_fn=lambda seconds: setattr(clock, "now", clock.now + seconds),
        clock=clock,
    )
    code = app.run(max_frames=2)
    assert code == 0
    output = buffer.getvalue()
    assert "HOTIRJAM AI 5 LIVE" in output
    assert "Price" in output and "--" in output
    assert "Feed Health" in output and "DISCONNECTED" in output
    assert "MARKET" in output
    assert "AI STATUS" in output
    assert "TRADE DECISION" in output
    assert "MEMORY" in output
    assert "ACCOUNT STATUS" in output
    assert "TODAY" in output
    assert "LIFETIME" in output
    assert "SIGNAL HISTORY" in output
    assert "SYSTEM" in output
    assert "PERFORMANCE" not in output
    assert "LAST SIGNAL" not in output
    assert "DECISION FOUNDATION" not in output


def test_app_updates_from_live_ingress(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text("", encoding="utf-8")
    ingress = LiveTickIngress(path)
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
        renderer=DashboardRenderer(width=100),
        display=TerminalDisplay(stream=buffer),
        refresh_seconds=0.25,
        poll_seconds=0.05,
        sleep_fn=lambda _: None,
        clock=FakeClock(0.0),
    )
    code = app.run(max_frames=1)
    assert code == 0
    output = buffer.getvalue()
    assert "Feed Health" in output and "HEALTHY" in output
    assert "20110.00" in output
    assert "DECISION FOUNDATION" not in output
    assert "Tick received" not in output


def test_app_prepare_and_shutdown_are_called(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    clock = FakeClock(0.0)

    class TrackingDisplay(TerminalDisplay):
        def prepare(self) -> None:
            calls.append("prepare")
            super().prepare()

        def shutdown(self) -> None:
            calls.append("shutdown")
            super().shutdown()

    display = TrackingDisplay(
        stream=io.StringIO(),
        ansi_supported=False,
        clear_command=lambda: None,
    )
    app = DashboardApp(
        controller=DashboardController(symbol="MNQ"),
        renderer=DashboardRenderer(),
        display=display,
        refresh_seconds=0.25,
        poll_seconds=0.05,
        sleep_fn=lambda seconds: setattr(clock, "now", clock.now + seconds),
        clock=clock,
    )
    assert app.run(max_frames=1) == 0
    assert calls == ["prepare", "shutdown"]


def test_app_rejects_non_positive_refresh() -> None:
    with pytest.raises(ValueError, match="refresh_seconds"):
        DashboardApp(refresh_seconds=0)


def test_cli_parser_defaults() -> None:
    args = build_arg_parser().parse_args([])
    assert args.symbol == "MNQ"
    assert args.refresh == 0.25
    assert args.poll == 0.05
    assert args.tick_file is None
    assert args.dom_file is None
    assert args.stall_seconds == 2.0
    assert args.stale_seconds == 5.0
    assert args.verbose is False


def test_cli_parser_verbose_flag() -> None:
    args = build_arg_parser().parse_args(["--verbose"])
    assert args.verbose is True


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
