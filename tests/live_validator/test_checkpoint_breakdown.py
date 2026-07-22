"""H-6.6.6 checkpoint / logger stage breakdown instrumentation."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    LiveValidatorApp,
    LiveValidatorController,
    SnapshotLogger,
)
from hotirjam_ai5.live_validator.idc_performance import render_performance_page
from hotirjam_ai5.live_validator.loop_timing import (
    LoopTimingSnapshot,
    StageBreakdown,
    TimingSeverity,
    begin_loop_sample,
    finish_loop_sample,
    latest_loop_timing,
    reset_loop_timing_for_tests,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.objective import ConfirmedSwing
from hotirjam_ai5.objective_diagnostics import (
    ObjectiveDiagnosticsInputs,
    PersistentStructuralHierarchy,
)


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
    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        return None


def test_hierarchy_checkpoint_breakdown_stages(tmp_path: Path) -> None:
    reset_loop_timing_for_tests()
    path = tmp_path / "hierarchy.json"
    hierarchy = PersistentStructuralHierarchy(checkpoint_path=path)
    begin_loop_sample()
    hierarchy.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=0.25,
            confirmed_highs=(ConfirmedSwing(price=110.0, strength=80.0, confirmed_at=1.0),),
            confirmed_lows=(ConfirmedSwing(price=90.0, strength=80.0, confirmed_at=1.0),),
            timestamp=1.0,
        )
    )
    # Force a checkpoint write even if evaluate already wrote one.
    hierarchy.checkpoint(path)
    finish_loop_sample()
    snap = latest_loop_timing()
    assert snap is not None
    assert snap.hierarchy_breakdown is not None
    bd = snap.hierarchy_breakdown
    assert bd.collect_ms is not None and bd.collect_ms >= 0.0
    assert bd.build_ms is not None and bd.build_ms >= 0.0
    assert bd.serialize_ms is not None and bd.serialize_ms >= 0.0
    assert bd.write_ms is not None and bd.write_ms >= 0.0
    assert bd.flush_ms is not None and bd.flush_ms >= 0.0


def test_snapshot_logger_breakdown_stages(tmp_path: Path) -> None:
    reset_loop_timing_for_tests()
    logger = SnapshotLogger(tmp_path / "frames.ndjson")
    begin_loop_sample()
    logger.log(ArchitecturePipeline.empty_frame(timestamp=1.0))
    finish_loop_sample()
    snap = latest_loop_timing()
    assert snap is not None
    assert snap.logging_breakdown is not None
    bd = snap.logging_breakdown
    assert bd.collect_ms is None  # NOT APPLICABLE
    assert bd.build_ms is not None and bd.build_ms >= 0.0
    assert bd.serialize_ms is not None and bd.serialize_ms >= 0.0
    assert bd.write_ms is not None and bd.write_ms >= 0.0
    assert bd.flush_ms is None  # NOT APPLICABLE


def test_performance_page_shows_breakdown() -> None:
    snap = LoopTimingSnapshot(
        loop_ms=20.0,
        poll_ms=15.0,
        keyboard_ms=0.5,
        render_ms=1.0,
        sleep_ms=3.0,
        checkpoint_ms=8.0,
        initiative_checkpoint_ms=1.0,
        hierarchy_checkpoint_ms=7.0,
        logging_ms=5.0,
        start_time=1.0,
        end_time=1.02,
        poll_severity=TimingSeverity.OK,
        keyboard_severity=TimingSeverity.OK,
        render_severity=TimingSeverity.OK,
        sleep_severity=TimingSeverity.OK,
        checkpoint_severity=TimingSeverity.OK,
        initiative_checkpoint_severity=TimingSeverity.OK,
        hierarchy_checkpoint_severity=TimingSeverity.OK,
        logging_severity=TimingSeverity.OK,
        loop_severity=TimingSeverity.OK,
        hierarchy_breakdown=StageBreakdown(
            collect_ms=0.1,
            build_ms=4.0,
            serialize_ms=2.0,
            write_ms=0.5,
            flush_ms=0.4,
        ),
        logging_breakdown=StageBreakdown(
            collect_ms=None,
            build_ms=3.0,
            serialize_ms=1.5,
            write_ms=0.5,
            flush_ms=None,
        ),
    )
    text = render_performance_page(snap, feed_status="LIVE")
    assert "Hierarchy Checkpoint" in text
    assert "Collect........." in text
    assert "Build..........." in text
    assert "Serialize......." in text
    assert "Write..........." in text
    assert "Flush..........." in text
    assert "Snapshot Logger" in text
    assert "NOT APPLICABLE" in text
    assert "4.00 ms" in text


def test_performance_page_unavailable_breakdown() -> None:
    text = render_performance_page(None)
    assert "Hierarchy Checkpoint" in text
    assert "Snapshot Logger" in text
    assert "NOT AVAILABLE" in text


def test_live_path_records_breakdowns(tmp_path: Path) -> None:
    reset_loop_timing_for_tests()

    class FakeIngress:
        def __init__(self) -> None:
            self._ts = 0.0

        def poll(self) -> tuple[LiveTick, ...]:
            self._ts += 1.0
            return (_tick(100.0 + self._ts, ts=self._ts),)

    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        ),
        logger=SnapshotLogger(tmp_path / "frames.ndjson"),
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
    assert snap.logging_breakdown is not None
    assert snap.logging_breakdown.build_ms is not None
    # Hierarchy checkpoint may or may not fire every tick; logging always does.
    text = render_performance_page(snap, feed_status="LIVE")
    assert "Snapshot Logger" in text
    assert "Build..........." in text
