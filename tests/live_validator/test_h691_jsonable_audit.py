"""H-6.9.1 evidence: why _jsonable(objective_diagnostics) is hottest."""

from __future__ import annotations

import json
from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import LiveValidatorController, SnapshotLogger
from hotirjam_ai5.live_validator.jsonable_audit import (
    jsonable_audit_history,
    latest_jsonable_audit,
    merge_history_verdict,
    render_jsonable_audit_report,
    reset_jsonable_audit_for_tests,
)
from hotirjam_ai5.live_validator.logger import _jsonable
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
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
            ConfirmedSwing(price=101.0 + i * 0.25, strength=90.0 - i, confirmed_at=float(i + 1))
            for i in range(12)
        ]
        self._lows = [
            ConfirmedSwing(price=99.0 - i * 0.25, strength=90.0 - i, confirmed_at=float(i + 1))
            for i in range(12)
        ]


def test_h691_audit_output_matches_jsonable(tmp_path: Path) -> None:
    """Historical H-6.9.1: audited _jsonable(R) matches plain _jsonable(R)."""
    from hotirjam_ai5.live_validator.jsonable_audit import jsonable_with_audit

    reset_jsonable_audit_for_tests()
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        ),
        swing_confirmer=_SeededSwings(),
        logger=SnapshotLogger(tmp_path / "frames.ndjson"),
    )
    frame = controller.on_tick(_tick(98.5, ts=1.0))
    assert frame.objective_diagnostics is not None
    audited = jsonable_with_audit(frame.objective_diagnostics)
    classic = _jsonable(frame.objective_diagnostics)
    assert audited == classic
    snap = latest_jsonable_audit()
    assert snap is not None
    assert snap.dataclass_count >= 1
    # Logger must not emit R (Alternative E).
    line = (tmp_path / "frames.ndjson").read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "objective_diagnostics" not in json.loads(line)


def test_h691_diagnostics_serialization_evidence(tmp_path: Path) -> None:
    """Historical evidence: R serialization cost via direct audit (not logger)."""
    from hotirjam_ai5.live_validator.jsonable_audit import jsonable_with_audit

    reset_jsonable_audit_for_tests()
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        ),
        swing_confirmer=_SeededSwings(),
        logger=SnapshotLogger(tmp_path / "frames.ndjson"),
    )
    for i in range(1, 16):
        frame = controller.on_tick(_tick(98.5 - (i % 4) * 0.25, ts=float(i)))
        if frame.objective_diagnostics is not None:
            jsonable_with_audit(frame.objective_diagnostics)

    history = jsonable_audit_history()
    assert len(history) >= 10
    snap = latest_jsonable_audit()
    assert snap is not None
    assert snap.top_hottest_paths
    assert snap.object_count > 10
    assert snap.cause_class in {
        "Repeated conversion",
        "Duplicate traversal",
        "Large object",
        "Deep recursion",
        "Large collections",
        "Other",
    }
    cause, verdict = merge_history_verdict(history)
    assert verdict in {"CONFIRMED", "PARTIALLY CONFIRMED", "REJECTED"}
    text = render_jsonable_audit_report(snap)
    assert "VERDICT:" in text
    assert "TOP 20 HOTTEST" in text
    (tmp_path / "H691_EVIDENCE.txt").write_text(text, encoding="utf-8")
