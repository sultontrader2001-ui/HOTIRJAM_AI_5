"""Phase A — Objective Engineering Validation workflow tests.

Does not change Objective Engine. Does not claim Formal Validation.
"""

from __future__ import annotations

import io
from pathlib import Path

from hotirjam_ai5.objective.objective_snapshot import (
    ObjectivePersistenceState,
    ObjectiveSnapshot,
)
from hotirjam_ai5.objective_engineering.anomalies import AnomalyCode
from hotirjam_ai5.objective_engineering.app import build_arg_parser, main
from hotirjam_ai5.objective_engineering.recorder import ObjectiveEngineeringRecorder
from hotirjam_ai5.objective_engineering.reasons import ReasonClass, infer_side_reason
from hotirjam_ai5.objective_engineering.session import EngineeringValidationSession


def _snap(
    *,
    ts: float,
    price: float = 100.0,
    high: float | None = None,
    high_dist: float | None = None,
    high_state: ObjectivePersistenceState | None = None,
    low: float | None = None,
    low_dist: float | None = None,
    low_state: ObjectivePersistenceState | None = None,
) -> ObjectiveSnapshot:
    return ObjectiveSnapshot(
        nearest_high_price=high,
        nearest_high_distance_ticks=high_dist,
        nearest_high_strength=50.0 if high is not None else None,
        nearest_low_price=low,
        nearest_low_distance_ticks=low_dist,
        nearest_low_strength=50.0 if low is not None else None,
        current_price=price,
        timestamp=ts,
        high_state=high_state,
        low_state=low_state,
    )


def test_infer_replace_nearer_and_unexpected() -> None:
    nearer = infer_side_reason(
        previous_price=110.0,
        previous_distance=40.0,
        previous_state=ObjectivePersistenceState.PERSISTED,
        current_price=105.0,
        current_distance=20.0,
        current_state=ObjectivePersistenceState.REPLACED,
    )
    assert nearer is ReasonClass.NEARER_ELIGIBLE

    unexpected = infer_side_reason(
        previous_price=105.0,
        previous_distance=20.0,
        previous_state=ObjectivePersistenceState.PERSISTED,
        current_price=110.0,
        current_distance=40.0,
        current_state=ObjectivePersistenceState.REPLACED,
    )
    assert unexpected is ReasonClass.UNEXPECTED_NOT_NEARER


def test_infer_breach_and_new() -> None:
    assert (
        infer_side_reason(
            previous_price=110.0,
            previous_distance=10.0,
            previous_state=ObjectivePersistenceState.PERSISTED,
            current_price=None,
            current_distance=None,
            current_state=ObjectivePersistenceState.BREACHED,
        )
        is ReasonClass.CONFIRMED_BROKEN
    )
    assert (
        infer_side_reason(
            previous_price=None,
            previous_distance=None,
            previous_state=None,
            current_price=110.0,
            current_distance=10.0,
            current_state=ObjectivePersistenceState.NEW,
        )
        is ReasonClass.FIRST_ASSIGNMENT
    )


def test_recorder_collects_sample_change_and_highlights_unexpected_replace(
    tmp_path: Path,
) -> None:
    err = io.StringIO()
    recorder = ObjectiveEngineeringRecorder(
        samples_path=tmp_path / "samples.ndjson",
        changes_path=tmp_path / "changes.ndjson",
        anomalies_path=tmp_path / "anomalies.ndjson",
        anomaly_stream=err,
    )
    recorder.observe(
        _snap(
            ts=1.0,
            high=110.0,
            high_dist=40.0,
            high_state=ObjectivePersistenceState.NEW,
            low=90.0,
            low_dist=40.0,
            low_state=ObjectivePersistenceState.NEW,
        )
    )
    recorder.observe(
        _snap(
            ts=2.0,
            high=110.0,
            high_dist=40.0,
            high_state=ObjectivePersistenceState.PERSISTED,
            low=90.0,
            low_dist=40.0,
            low_state=ObjectivePersistenceState.PERSISTED,
        )
    )
    anomalies = recorder.observe(
        _snap(
            ts=3.0,
            high=120.0,
            high_dist=80.0,
            high_state=ObjectivePersistenceState.REPLACED,
            low=90.0,
            low_dist=40.0,
            low_state=ObjectivePersistenceState.PERSISTED,
        )
    )
    assert len(recorder.samples) == 3
    assert any(c.side == "HIGH" and c.to_state == "REPLACED" for c in recorder.changes)
    assert any(a.code == AnomalyCode.UNEXPECTED_REPLACEMENT.value for a in anomalies)
    assert "OBJECTIVE_EV_ANOMALY" in err.getvalue()
    assert (tmp_path / "samples.ndjson").read_text(encoding="utf-8").count("\n") == 3
    assert (tmp_path / "anomalies.ndjson").read_text(encoding="utf-8").strip()


def test_impossible_transition_and_invalid_none() -> None:
    recorder = ObjectiveEngineeringRecorder(anomaly_stream=io.StringIO())
    recorder.observe(_snap(ts=1.0))
    anomalies = recorder.observe(
        _snap(
            ts=2.0,
            high=110.0,
            high_dist=10.0,
            high_state=ObjectivePersistenceState.REPLACED,
        )
    )
    assert any(a.code == AnomalyCode.IMPOSSIBLE_TRANSITION.value for a in anomalies)

    recorder2 = ObjectiveEngineeringRecorder(anomaly_stream=io.StringIO())
    anomalies2 = recorder2.observe(
        _snap(
            ts=1.0,
            high=None,
            high_state=ObjectivePersistenceState.PERSISTED,
        )
    )
    assert any(a.code == AnomalyCode.INVALID_NONE.value for a in anomalies2)


def test_side_coupling_and_flicker() -> None:
    recorder = ObjectiveEngineeringRecorder(anomaly_stream=io.StringIO(), flicker_window=3)
    recorder.observe(
        _snap(
            ts=1.0,
            high=110.0,
            high_dist=10.0,
            high_state=ObjectivePersistenceState.PERSISTED,
            low=90.0,
            low_dist=10.0,
            low_state=ObjectivePersistenceState.PERSISTED,
        )
    )
    coupled = recorder.observe(
        _snap(
            ts=2.0,
            high=111.0,
            high_dist=8.0,
            high_state=ObjectivePersistenceState.REPLACED,
            low=89.0,
            low_dist=8.0,
            low_state=ObjectivePersistenceState.REPLACED,
        )
    )
    assert any(a.code == AnomalyCode.SIDE_COUPLING.value for a in coupled)

    flicker_rec = ObjectiveEngineeringRecorder(anomaly_stream=io.StringIO(), flicker_window=3)
    flicker_rec.observe(
        _snap(ts=1.0, high=110.0, high_dist=10.0, high_state=ObjectivePersistenceState.NEW)
    )
    flicker_rec.observe(
        _snap(
            ts=2.0,
            high=112.0,
            high_dist=5.0,
            high_state=ObjectivePersistenceState.REPLACED,
        )
    )
    flickered = flicker_rec.observe(
        _snap(
            ts=3.0,
            high=110.0,
            high_dist=10.0,
            high_state=ObjectivePersistenceState.REPLACED,
        )
    )
    assert any(a.code == AnomalyCode.UNEXPLAINED_FLICKER.value for a in flickered)


def test_session_demo_writes_report(tmp_path: Path) -> None:
    from hotirjam_ai5.live_data.tick import LiveTick

    session = EngineeringValidationSession(
        out_dir=tmp_path / "ev",
        anomaly_stream=io.StringIO(),
    )
    ticks = [
        LiveTick(
            timestamp=1_700_000_000.0 + i,
            symbol="MNQ",
            last_price=18000.0 + (i % 5) * 0.25,
            bid=17999.75,
            ask=18000.25,
            volume=1.0,
        )
        for i in range(40)
    ]
    report = session.run_ticks(ticks, max_samples=40)
    assert report.workflow_verdict == "PASS"
    assert report.sample_count >= 1
    assert (tmp_path / "ev" / "session_report.txt").is_file()
    assert (tmp_path / "ev" / "samples.ndjson").is_file()


def test_cli_demo_exits_zero(tmp_path: Path) -> None:
    out = tmp_path / "cli_ev"
    code = main(["--demo", "--demo-ticks", "30", "--out-dir", str(out)])
    assert code == 0
    assert (out / "session_report.txt").is_file()


def test_cli_help_mentions_not_certify() -> None:
    parser = build_arg_parser()
    help_text = parser.format_help()
    assert "Does NOT certify" in help_text or "NOT" in help_text
