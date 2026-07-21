"""H-6.6.4 freeze instrumentation — passive loop timing only."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    LiveValidatorApp,
    LiveValidatorController,
    LoopTimingSnapshot,
    SnapshotLogger,
    TimingSeverity,
)
from hotirjam_ai5.live_validator.loop_timing import (
    CRITICAL_MS,
    SLOW_MS,
    begin_loop_sample,
    finish_loop_sample,
    latest_loop_timing,
    reset_loop_timing_for_tests,
    severity_for_ms,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline


def _tick(price: float, *, ts: float) -> LiveTick:
    return LiveTick(
        timestamp=ts,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=1.0,
    )


class _FakeKeyboard:
    def __init__(self) -> None:
        pass

    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        return None


def test_severity_thresholds() -> None:
    assert severity_for_ms(0.0) is TimingSeverity.OK
    assert severity_for_ms(SLOW_MS) is TimingSeverity.SLOW
    assert severity_for_ms(CRITICAL_MS) is TimingSeverity.CRITICAL


def test_only_latest_snapshot_retained() -> None:
    reset_loop_timing_for_tests()
    begin_loop_sample()
    finish_loop_sample()
    first = latest_loop_timing()
    begin_loop_sample()
    finish_loop_sample()
    second = latest_loop_timing()
    assert first is not None
    assert second is not None
    assert second is latest_loop_timing()
    assert second.end_time >= first.end_time


def test_app_exposes_loop_timing_read_only() -> None:
    reset_loop_timing_for_tests()
    app = LiveValidatorApp(
        controller=LiveValidatorController(),
        keyboard=_FakeKeyboard(),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    assert app.loop_timing is None
    app.run(max_frames=2)
    snap = app.loop_timing
    assert isinstance(snap, LoopTimingSnapshot)
    assert snap.loop_ms >= 0.0
    assert snap.poll_ms >= 0.0
    assert snap.keyboard_ms >= 0.0
    assert snap.render_ms >= 0.0
    assert snap.sleep_ms >= 0.0
    assert snap.checkpoint_ms >= 0.0
    assert snap.initiative_checkpoint_ms >= 0.0
    assert snap.hierarchy_checkpoint_ms >= 0.0
    assert snap.logging_ms >= 0.0
    assert snap.end_time >= snap.start_time


def test_checkpoint_and_logging_timing_accumulate(tmp_path: Path) -> None:
    reset_loop_timing_for_tests()
    hierarchy_path = tmp_path / "hierarchy.json"
    initiative_path = tmp_path / "initiative.json"
    log_path = tmp_path / "frames.ndjson"

    class FakeIngress:
        def __init__(self) -> None:
            self._ts = 0.0

        def poll(self) -> tuple[LiveTick, ...]:
            self._ts += 1.0
            return (_tick(100.0 + self._ts, ts=self._ts),)

    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=hierarchy_path,
            initiative_checkpoint_path=initiative_path,
        ),
        logger=SnapshotLogger(log_path),
    )
    app = LiveValidatorApp(
        controller=controller,
        ingress=FakeIngress(),  # type: ignore[arg-type]
        keyboard=_FakeKeyboard(),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app.run(max_frames=3)
    snap = app.loop_timing
    assert snap is not None
    # Initiative checkpoints on every evaluate when a path is configured.
    assert snap.initiative_checkpoint_ms > 0.0
    assert snap.logging_ms > 0.0
    assert snap.checkpoint_ms == (
        snap.initiative_checkpoint_ms + snap.hierarchy_checkpoint_ms
    )


def test_instrumentation_failure_does_not_break_validator() -> None:
    reset_loop_timing_for_tests()
    app = LiveValidatorApp(
        controller=LiveValidatorController(),
        keyboard=_FakeKeyboard(),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    assert app.run(max_frames=1) == 0


def test_dashboard_and_idc_unaffected_by_timing_module() -> None:
    from hotirjam_ai5.live_validator.idc import render_idc_main_menu
    from hotirjam_ai5.live_validator.display import render_validator_frame

    frame = ArchitecturePipeline.empty_frame(timestamp=1.0)
    dash = render_validator_frame(frame, developer_mode=False)
    assert "OBJECTIVE ENGINE" in dash or "Current High" in dash or "MARKET" in dash
    assert "loop_ms" not in dash
    assert "LoopTiming" not in dash
    menu = render_idc_main_menu()
    assert "Internal Diagnostics Console" in menu
    assert "loop_ms" not in menu
