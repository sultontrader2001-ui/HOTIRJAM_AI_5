"""H-6.6.7 serialization footprint diagnostics."""

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
    HierarchyFootprint,
    LoggingFootprint,
    LoopTimingSnapshot,
    SectionSize,
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


def test_hierarchy_footprint_counts_and_size(tmp_path: Path) -> None:
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
    hierarchy.checkpoint(path)
    finish_loop_sample()
    snap = latest_loop_timing()
    assert snap is not None
    assert snap.hierarchy_footprint is not None
    fp = snap.hierarchy_footprint
    assert fp.registry_entries >= 1
    assert fp.hierarchy_nodes == fp.registry_entries
    assert fp.journal_entries >= 1
    assert fp.snapshot_object_count == fp.registry_entries
    assert fp.json_size_bytes > 0
    assert fp.json_size_mb >= 0.0
    assert fp.largest_section is not None
    assert fp.section_sizes
    assert path.stat().st_size == fp.json_size_bytes


def test_logging_footprint_from_existing_line(tmp_path: Path) -> None:
    reset_loop_timing_for_tests()
    logger = SnapshotLogger(tmp_path / "frames.ndjson")
    begin_loop_sample()
    logger.log(ArchitecturePipeline.empty_frame(timestamp=1.0))
    finish_loop_sample()
    snap = latest_loop_timing()
    assert snap is not None
    assert snap.logging_footprint is not None
    fp = snap.logging_footprint
    assert fp.frame_object_count >= 1
    assert fp.json_size_bytes > 0
    assert "objective" in fp.top_level_sections or len(fp.top_level_sections) > 0
    assert fp.largest_section is not None


def test_performance_page_shows_footprint() -> None:
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
        hierarchy_breakdown=StageBreakdown(0.1, 4.0, 2.0, 0.5, 0.4),
        logging_breakdown=StageBreakdown(None, 3.0, 1.5, 0.5, None),
        hierarchy_footprint=HierarchyFootprint(
            registry_entries=1326,
            hierarchy_nodes=1326,
            journal_entries=27574,
            snapshot_object_count=1326,
            json_size_bytes=50_554_470,
            section_sizes=(
                SectionSize("journal", 40_000_000),
                SectionSize("records", 10_000_000),
            ),
            largest_section="journal",
            largest_section_bytes=40_000_000,
        ),
        logging_footprint=LoggingFootprint(
            frame_object_count=42,
            top_level_sections=("objective", "initiative"),
            json_size_bytes=20_342_784,
            section_sizes=(
                SectionSize("objective_diagnostics", 18_000_000),
                SectionSize("objective", 1_000_000),
            ),
            largest_section="objective_diagnostics",
            largest_section_bytes=18_000_000,
        ),
    )
    text = render_performance_page(snap, feed_status="LIVE")
    assert "Hierarchy Footprint" in text
    assert "Registry........ 1326" in text
    assert "Journal......... 27574" in text
    assert "48.21 MB" in text or "48.20 MB" in text
    assert "Largest Section. journal" in text
    assert "Snapshot Logger Footprint" in text
    assert "objective_diagnostics" in text
    assert "19.40 MB" in text or "19.39 MB" in text


def test_live_path_exposes_logging_footprint(tmp_path: Path) -> None:
    reset_loop_timing_for_tests()

    class FakeIngress:
        def __init__(self) -> None:
            self._ts = 0.0

        def poll(self) -> tuple[LiveTick, ...]:
            self._ts += 1.0
            return (_tick(100.0 + self._ts, ts=self._ts),)

    app = LiveValidatorApp(
        controller=LiveValidatorController(
            pipeline=ArchitecturePipeline(
                hierarchy_checkpoint_path=tmp_path / "h.json",
                initiative_checkpoint_path=tmp_path / "i.json",
            ),
            logger=SnapshotLogger(tmp_path / "frames.ndjson"),
        ),
        ingress=FakeIngress(),  # type: ignore[arg-type]
        keyboard=_FakeKeyboard(),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app.run(max_frames=2)
    snap = app.loop_timing
    assert snap is not None
    assert snap.logging_footprint is not None
    text = render_performance_page(snap)
    assert "Snapshot Logger Footprint" in text
    assert "JSON Size......." in text
