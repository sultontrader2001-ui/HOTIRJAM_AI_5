"""H-6.7.1 exclusive stage instrumentation — diagnostics only."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    LiveValidatorApp,
    LiveValidatorController,
    SnapshotLogger,
)
from hotirjam_ai5.live_validator.loop_timing import (
    begin_loop_sample,
    finish_loop_sample,
    latest_loop_timing,
    reset_loop_timing_for_tests,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.retention.files import enforce_ndjson_size_limit


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


def test_logging_exclusive_stages_are_non_overlapping(tmp_path: Path) -> None:
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
    assert snap.logging_exclusive is not None
    ex = snap.logging_exclusive
    exclusive_sum = (
        ex.build_ms
        + ex.serialize_ms
        + ex.write_ms
        + ex.flush_ms
        + ex.rotate_ms
        + ex.reopen_ms
    )
    # Exclusive stages are inside total; allow tiny timer overhead slack.
    assert exclusive_sum <= snap.logging_ms + 1.0
    assert ex.build_ms >= 0.0
    assert ex.serialize_ms >= 0.0
    assert ex.write_ms >= 0.0
    assert ex.flush_ms >= 0.0
    assert ex.rotate_ms >= 0.0
    assert ex.reopen_ms >= 0.0


def test_checkpoint_exclusive_stages_present(tmp_path: Path) -> None:
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
    assert snap.checkpoint_exclusive is not None
    ex = snap.checkpoint_exclusive
    assert ex.assemble_ms >= 0.0
    # Initiative contributes a distinct serialize; hierarchy is N/A alone but
    # combined path marks serialize applicable.
    assert ex.serialize_ms is not None
    assert ex.write_ms >= 0.0
    assert ex.flush_ms >= 0.0
    assert ex.fsync_ms >= 0.0
    assert ex.os_replace_ms >= 0.0
    exclusive_sum = (
        ex.assemble_ms
        + ex.serialize_ms
        + ex.write_ms
        + ex.flush_ms
        + ex.fsync_ms
        + ex.os_replace_ms
    )
    assert exclusive_sum <= snap.checkpoint_ms + 5.0


def test_tick_retention_exclusive_stages(tmp_path: Path) -> None:
    reset_loop_timing_for_tests()
    path = tmp_path / "ticks.ndjson"
    # Build a file large enough to trigger truncate of the consumed prefix.
    chunk = b'{"t":1}\n'
    path.write_bytes(chunk * 200)
    size = path.stat().st_size
    consumed = size // 2
    begin_loop_sample()
    assert (
        enforce_ndjson_size_limit(
            path, max_bytes=size // 4, consumed_offset=consumed
        )
        is True
    )
    finish_loop_sample()
    snap = latest_loop_timing()
    assert snap is not None
    assert snap.tick_retention is not None
    tr = snap.tick_retention
    assert tr.total_ms >= 0.0
    assert tr.stat_ms >= 0.0
    assert tr.read_ms >= 0.0
    assert tr.write_ms >= 0.0
    assert tr.fsync_ms >= 0.0
    assert tr.replace_ms >= 0.0
    exclusive_sum = (
        tr.stat_ms + tr.read_ms + tr.write_ms + tr.fsync_ms + tr.replace_ms
    )
    assert exclusive_sum <= tr.total_ms + 1.0
