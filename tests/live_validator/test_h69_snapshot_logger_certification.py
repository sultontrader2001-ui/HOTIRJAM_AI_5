"""H-6.9 Snapshot Logger certification evidence (instrumentation only)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import LiveValidatorController, SnapshotLogger
from hotirjam_ai5.live_validator.logger import _jsonable
from hotirjam_ai5.live_validator.loop_timing import (
    add_poll_ms,
    begin_loop_sample,
    finish_loop_sample,
    latest_loop_timing,
    reset_loop_timing_for_tests,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.live_validator.snapshot_logger_probe import (
    attach_correlation_to_last_sample,
    build_snapshot_logger_evidence_report,
    render_snapshot_logger_evidence_report,
    reset_snapshot_logger_probe_for_tests,
    snapshot_logger_samples,
)
from hotirjam_ai5.live_validator.swing_confirmer import SwingConfirmer
from hotirjam_ai5.objective import ConfirmedSwing


def _tick(price: float, *, ts: float) -> LiveTick:
    return LiveTick(
        timestamp=ts,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=1.0,
    )


class _SeededSwings(SwingConfirmer):
    def __init__(self) -> None:
        super().__init__()
        self._highs = [
            ConfirmedSwing(price=101.0, strength=90.0, confirmed_at=1.0),
            ConfirmedSwing(price=102.0, strength=85.0, confirmed_at=2.0),
        ]
        self._lows = [
            ConfirmedSwing(price=99.0, strength=90.0, confirmed_at=1.0),
            ConfirmedSwing(price=98.0, strength=85.0, confirmed_at=2.0),
        ]


def test_h69_logger_payload_excludes_runtime_report(tmp_path: Path) -> None:
    """H-6.9.4: logger emits P envelope; never full R / frame dump."""
    reset_snapshot_logger_probe_for_tests()
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        ),
        swing_confirmer=_SeededSwings(),
        logger=SnapshotLogger(tmp_path / "frames.ndjson"),
    )
    frame = controller.on_tick(_tick(98.5, ts=1.0))
    line = (tmp_path / "frames.ndjson").read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert "objective_diagnostics" not in payload
    assert payload.get("diagnostic_log_version") == 1
    assert isinstance(payload.get("diagnostic_log"), dict)
    assert "highs" not in payload["diagnostic_log"]
    assert "lows" not in payload["diagnostic_log"]
    # Full-frame dump would include R; logger must differ from naive _jsonable(frame).
    classic = json.dumps(_jsonable(frame), separators=(",", ":"), sort_keys=False)
    assert line != classic
    assert frame.diagnostic_log is not None


def test_h69_snapshot_logger_evidence_harness(tmp_path: Path) -> None:
    reset_snapshot_logger_probe_for_tests()
    reset_loop_timing_for_tests()
    log_path = tmp_path / "frames.ndjson"
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        ),
        swing_confirmer=_SeededSwings(),
        logger=SnapshotLogger(log_path),
    )

    n = 40
    for i in range(1, n + 1):
        begin_loop_sample()
        _t0 = time.perf_counter()
        price = 98.5 - (i % 5) * 0.25
        controller.on_tick(_tick(price, ts=float(i)))
        add_poll_ms((time.perf_counter() - _t0) * 1000.0)
        finish_loop_sample()
        snap = latest_loop_timing()
        assert snap is not None
        attach_correlation_to_last_sample(
            loop_ms=snap.loop_ms,
            poll_ms=snap.poll_ms,
            checkpoint_ms=snap.checkpoint_ms,
        )

    samples = snapshot_logger_samples()
    assert len(samples) == n
    report = build_snapshot_logger_evidence_report()
    assert report.samples
    assert report.hottest_phase is not None
    assert report.contribution_class in {"<10%", "10–25%", "25–50%", ">50%", "UNKNOWN"}
    assert report.verdict in {"CONFIRMED", "PARTIALLY CONFIRMED", "REJECTED"}
    assert report.mean_loop_ms is not None
    assert report.mean_logger_share_of_loop is not None

    text = render_snapshot_logger_evidence_report(report)
    assert "VERDICT:" in text
    assert "TIMING TABLE" in text
    evidence = tmp_path / "H69_EVIDENCE.txt"
    evidence.write_text(text, encoding="utf-8")
    assert evidence.exists()
