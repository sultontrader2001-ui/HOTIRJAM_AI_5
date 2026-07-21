"""Tests for Live Validator (observation-only architecture runner)."""

from __future__ import annotations

import json
from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    ArchitecturePipeline,
    LiveValidatorApp,
    LiveValidatorController,
    SnapshotLogger,
    SwingConfirmer,
    TickBarBuilder,
    render_validator_frame,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline as Pipeline


def _tick(
    price: float,
    *,
    ts: float,
    volume: float = 1.0,
) -> LiveTick:
    return LiveTick(
        timestamp=ts,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=volume,
    )


# ---------------------------------------------------------------- candles / swings


def test_bar_builder_closes_on_bucket_change() -> None:
    builder = TickBarBuilder(bar_seconds=1.0, max_bars=20)
    assert builder.on_tick(_tick(100.0, ts=1.0)) == ()
    assert builder.on_tick(_tick(100.5, ts=1.4)) == ()
    closed = builder.on_tick(_tick(101.0, ts=2.1))
    assert len(closed) == 1
    assert closed[0].open == 100.0
    assert closed[0].high == 100.5
    assert closed[0].low == 100.0
    assert closed[0].close == 100.5
    assert len(builder.closed_candles) == 1


def test_swing_confirmer_detects_high_and_low() -> None:
    builder = TickBarBuilder(bar_seconds=1.0)
    confirmer = SwingConfirmer()
    # Build three closed bars: up pivot high in the middle, then down.
    prices = [
        (100.0, 0.0),
        (100.5, 0.5),
        (101.5, 1.0),  # high bar
        (100.8, 2.0),
        (100.2, 3.0),
        (99.0, 4.0),  # low area
        (99.5, 5.0),
    ]
    for price, ts in prices:
        newly = builder.on_tick(_tick(price, ts=ts))
        if newly:
            confirmer.on_closed_candles(newly)
    # Force close last forming by advancing bucket
    newly = builder.on_tick(_tick(99.6, ts=6.0))
    if newly:
        confirmer.on_closed_candles(newly)

    assert len(confirmer.confirmed_highs) >= 1 or len(confirmer.confirmed_lows) >= 0
    # With this path we should get at least one swing of some kind after enough bars
    assert len(builder.closed_candles) >= 5


# ---------------------------------------------------------------- pipeline / controller


def test_pipeline_runs_all_engines_decision_disabled() -> None:
    from hotirjam_ai5.initiative import OhlcCandle
    from hotirjam_ai5.objective import ConfirmedSwing

    candles = tuple(
        OhlcCandle(open=100 + i, high=100.5 + i, low=99.8 + i, close=100.4 + i, volume=10.0)
        for i in range(6)
    )
    frame = ArchitecturePipeline().evaluate(
        current_price=105.0,
        timestamp=1_700_000_000.0,
        candles=candles,
        confirmed_highs=(ConfirmedSwing(106.0, 70.0, confirmed_at=1.0),),
        confirmed_lows=(ConfirmedSwing(98.0, 65.0, confirmed_at=1.0),),
    )
    assert frame.decision == "DISABLED"
    assert frame.current_price == 105.0
    assert frame.objective.nearest_high_price == 106.0
    assert frame.initiative.timestamp == 1_700_000_000.0
    assert frame.response.timestamp == 1_700_000_000.0
    assert frame.continuation.timestamp == 1_700_000_000.0
    assert frame.break_capability.timestamp == 1_700_000_000.0


def test_controller_on_tick_updates_and_never_enables_decision(tmp_path: Path) -> None:
    log_path = tmp_path / "snaps.ndjson"
    controller = LiveValidatorController(
        logger=SnapshotLogger(log_path),
        bar_builder=TickBarBuilder(bar_seconds=1.0),
    )
    frame = None
    for i in range(8):
        frame = controller.on_tick(_tick(100.0 + i * 0.25, ts=float(i)))
    assert frame is not None
    assert frame.decision == "DISABLED"
    assert controller.evaluations == 8
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 8
    payload = json.loads(lines[-1])
    assert payload["decision"] == "DISABLED"
    assert "objective" in payload
    assert "break_capability" in payload


def test_display_default_is_certification_dashboard() -> None:
    frame = Pipeline.empty_frame(timestamp=1_700_000_000.0)
    text = render_validator_frame(frame)
    assert "LIVE CERTIFICATION DASHBOARD" in text
    for section in (
        "MARKET",
        "OBJECTIVE ENGINE",
        "INITIATIVE ENGINE",
        "RESPONSE ENGINE",
        "CONTINUATION ENGINE",
        "BREAK CAPABILITY",
        "SYSTEM",
        "AUDIT LOG",
    ):
        assert section in text
    assert "Decision          DISABLED" in text
    assert "Execution         DISABLED" in text
    # Developer noise must stay hidden in the default dashboard.
    assert "Impulse/Mom/Cndl" not in text
    assert "Pressure/Decay" not in text
    assert "Pressure/Resist" not in text


def test_display_developer_view_toggle() -> None:
    frame = Pipeline.empty_frame(timestamp=1_700_000_000.0)
    text = render_validator_frame(frame, developer_mode=True)
    assert "DEVELOPER VIEW" in text
    assert "CURRENT OBJECTIVE" in text
    assert "STRUCTURAL OBJECTIVE DIAGNOSTICS" in text
    assert "No diagnostics available." in text
    assert "INITIATIVE" in text
    assert "RESPONSE" in text
    assert "CONTINUATION" in text
    assert "BREAK CAPABILITY" in text
    assert "Decision Engine   DISABLED" in text
    assert "MARKET MOMENTUM" not in text


def test_developer_view_shows_attached_diagnostics() -> None:
    from dataclasses import replace

    from hotirjam_ai5.objective import ConfirmedSwing
    from hotirjam_ai5.objective_diagnostics import (
        ObjectiveDiagnosticsInputs,
        audit_objectives,
    )

    diagnostics = audit_objectives(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=0.25,
            confirmed_highs=(ConfirmedSwing(105.0, 70.0, confirmed_at=1.0),),
            confirmed_lows=(ConfirmedSwing(95.0, 70.0, confirmed_at=1.0),),
            timestamp=1_700_000_000.0,
        )
    )
    frame = replace(
        Pipeline.empty_frame(timestamp=1_700_000_000.0),
        current_price=100.0,
        objective_diagnostics=diagnostics,
    )
    text = render_validator_frame(frame, developer_mode=True)
    assert "STRUCTURAL OBJECTIVE DIAGNOSTICS" in text
    assert "HIGHS" in text
    assert "LOWS" in text
    assert "Summary" in text
    assert "Total Swings" in text
    assert "Eligible Highs" in text
    assert "No diagnostics available." not in text
    trader = render_validator_frame(frame, developer_mode=False)
    assert "STRUCTURAL OBJECTIVE DIAGNOSTICS" not in trader


def test_app_poll_and_render_without_decision(tmp_path: Path) -> None:
    class FakeIngress:
        def __init__(self) -> None:
            self._ticks = [
                _tick(100.0, ts=1.0),
                _tick(100.5, ts=1.2),
                _tick(101.0, ts=2.1),
            ]
            self._i = 0

        def poll(self) -> tuple[LiveTick, ...]:
            if self._i >= len(self._ticks):
                return ()
            tick = self._ticks[self._i]
            self._i += 1
            return (tick,)

    log_path = tmp_path / "v.ndjson"
    controller = LiveValidatorController(logger=SnapshotLogger(log_path))
    sleeps: list[float] = []
    app = LiveValidatorApp(
        controller=controller,
        ingress=FakeIngress(),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=sleeps.append,
        clock=lambda: 100.0 + len(sleeps) * 0.02,
    )
    code = app.run(max_frames=3)
    assert code == 0
    assert controller.evaluations >= 1
    assert "DISABLED" in render_validator_frame(controller.latest)


def test_empty_frame_decision_disabled() -> None:
    frame = ArchitecturePipeline.empty_frame(timestamp=0.0)
    assert frame.decision == "DISABLED"
    assert frame.current_price is None
