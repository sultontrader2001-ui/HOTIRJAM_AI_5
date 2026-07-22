"""H-6.8.2 — Alternative 1: reuse ObjectiveAuditReport; max 1 hierarchy.evaluate/tick."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import LiveValidatorController, SnapshotLogger
from hotirjam_ai5.live_validator.logger import _jsonable
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.live_validator.swing_confirmer import SwingConfirmer
from hotirjam_ai5.objective import ConfirmedSwing
from hotirjam_ai5.objective_diagnostics.hierarchy_evaluate_probe import (
    build_hierarchy_evaluate_probe_stats,
    hierarchy_evaluate_call_records,
    reset_hierarchy_evaluate_probe_for_tests,
)
from hotirjam_ai5.objective_diagnostics.models import ObjectiveAuditReport


def _tick(price: float, *, ts: float) -> LiveTick:
    return LiveTick(
        timestamp=ts,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=1.0,
    )


def _fingerprint_report(report: ObjectiveAuditReport | None) -> str:
    """Stable fingerprint of an ObjectiveAuditReport (or None)."""
    if report is None:
        return hashlib.sha256(b"NONE").hexdigest()
    payload = _jsonable(report)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class _SeededSwings(SwingConfirmer):
    def __init__(self) -> None:
        super().__init__()
        self._highs = [
            ConfirmedSwing(price=101.0, strength=90.0, confirmed_at=1.0),
        ]
        self._lows = [
            ConfirmedSwing(price=99.0, strength=90.0, confirmed_at=1.0),
        ]


def test_h682_max_one_hierarchy_evaluate_per_tick(tmp_path: Path) -> None:
    reset_hierarchy_evaluate_probe_for_tests()
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        ),
        swing_confirmer=_SeededSwings(),
    )
    for i, px in enumerate([98.5, 98.4, 100.0, 100.5, 101.5], start=1):
        controller.on_tick(_tick(px, ts=float(i)))

    stats = build_hierarchy_evaluate_probe_stats()
    assert stats.accepted_ticks == 5
    assert stats.hierarchy_evaluations == 5
    assert stats.average_evaluations_per_tick == 1.0
    assert stats.maximum_evaluations_per_tick == 1
    assert stats.minimum_evaluations_per_tick == 1
    assert stats.distribution == {1: 5}
    assert stats.ticks_with_multiple_evaluations == 0
    assert stats.verdict == "REJECTED"  # REJECTED = no multi-eval (probe naming)


def test_h682_report_identity_and_fingerprints(tmp_path: Path) -> None:
    reset_hierarchy_evaluate_probe_for_tests()
    log_path = tmp_path / "frames.ndjson"
    pipeline = ArchitecturePipeline(
        hierarchy_checkpoint_path=tmp_path / "h.json",
        initiative_checkpoint_path=tmp_path / "i.json",
    )
    controller = LiveValidatorController(
        pipeline=pipeline,
        swing_confirmer=_SeededSwings(),
        logger=SnapshotLogger(log_path),
    )
    frame = controller.on_tick(_tick(98.5, ts=1.0))

    engine_report = pipeline.objective_engine.last_audit_report
    frame_report = frame.objective_diagnostics
    assert engine_report is not None
    assert frame_report is not None
    # Same instance — single source of truth.
    assert frame_report is engine_report

    fp_engine = _fingerprint_report(engine_report)
    fp_frame = _fingerprint_report(frame_report)
    assert fp_engine == fp_frame

    # H-6.9.4: logger serializes projection P, not runtime report R.
    # Frame still carries identical R (engine identity above).
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert "objective_diagnostics" not in payload
    assert "diagnostic_log_version" in payload
    assert "diagnostic_log" in payload
    assert frame.diagnostic_log is not None
    fp_p = hashlib.sha256(
        json.dumps(
            frame.diagnostic_log.as_log_envelope(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    fp_s = hashlib.sha256(
        json.dumps(
            {
                "diagnostic_log_version": payload["diagnostic_log_version"],
                "diagnostic_log": payload["diagnostic_log"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert fp_p == fp_s
    assert fp_p != fp_engine  # FP-R ≢ FP-P by design

    # Exactly one hierarchy.evaluate for this accepted tick.
    records = [r for r in hierarchy_evaluate_call_records() if r.tick_id == 1]
    assert len(records) == 1
    assert records[0].caller.startswith("objective_engine.py:")


def test_h682_architecture_outputs_present(tmp_path: Path) -> None:
    """Objective / Response / Continuation / Break still produce snapshots."""
    reset_hierarchy_evaluate_probe_for_tests()
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        ),
        swing_confirmer=_SeededSwings(),
    )
    frame = controller.on_tick(_tick(100.0, ts=1.0))
    assert frame.objective is not None
    assert frame.initiative is not None
    assert frame.response is not None
    assert frame.continuation is not None
    assert frame.break_capability is not None
    assert frame.decision == "DISABLED"
    assert frame.objective_diagnostics is not None
