"""Tests for Entry Timing Audit (Sprint 37) — analytics only."""

from __future__ import annotations

from pathlib import Path

import pytest

from hotirjam_ai5.entry_timing import (
    EntryTimingAuditor,
    TimingClass,
    TimingLogWriter,
    classify_timing,
    signed_points,
)
from hotirjam_ai5.entry_timing.models import CheckpointSample
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _decision(decision: TradeDecision, *, timestamp: float) -> TradeDecisionSnapshot:
    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=decision,
        reason="test",
        next_action="Execution Engine",
    )


def _run_path(
    auditor: EntryTimingAuditor,
    clock: FakeClock,
    *,
    decision: TradeDecision,
    entry_price: float,
    path: list[tuple[float, float]],
) -> object:
    """path items are (age_seconds, price)."""
    clock.now = 1_000.0
    auditor.observe(
        _decision(decision, timestamp=clock.now),
        current_price=entry_price,
        timestamp=clock.now,
    )
    for age, price in path:
        clock.now = 1_000.0 + age
        auditor.update_price(current_price=price, timestamp=clock.now)
    assert auditor.completed
    return auditor.completed[-1]


def test_signed_points_buy_and_sell() -> None:
    assert signed_points(decision="BUY_INTERNAL", entry_price=100.0, current_price=105.0) == 5.0
    assert signed_points(decision="SELL_INTERNAL", entry_price=100.0, current_price=95.0) == 5.0


def test_normal_buy_continues_after_entry(tmp_path: Path) -> None:
    clock = FakeClock()
    auditor = EntryTimingAuditor(
        clock=clock,
        log_writer=TimingLogWriter(tmp_path / "t.jsonl"),
        id_factory=lambda: "n1",
    )
    # Strong continuation — NORMAL
    record = _run_path(
        auditor,
        clock,
        decision=TradeDecision.BUY_INTERNAL,
        entry_price=29050.25,
        path=[
            (30, 29051.50),
            (60, 29054.00),
            (120, 29056.75),
            (180, 29060.00),
            (300, 29064.50),
        ],
    )
    assert record.timing_class is TimingClass.NORMAL
    assert record.mfe is not None and record.mfe >= 14.0
    assert record.mae is not None and record.mae >= -0.01
    by_offset = {c.offset_seconds: c.points for c in record.checkpoints}
    assert by_offset[30] == pytest.approx(1.25)
    assert by_offset[300] == pytest.approx(14.25)


def test_early_buy_adverse_then_recovery(tmp_path: Path) -> None:
    clock = FakeClock()
    auditor = EntryTimingAuditor(
        clock=clock,
        log_writer=TimingLogWriter(tmp_path / "e.jsonl"),
        id_factory=lambda: "e1",
    )
    record = _run_path(
        auditor,
        clock,
        decision=TradeDecision.BUY_INTERNAL,
        entry_price=100.0,
        path=[
            (10, 97.0),   # adverse
            (30, 97.5),
            (60, 98.0),
            (120, 101.0),
            (180, 103.0),
            (300, 105.0),  # recovered
        ],
    )
    assert record.timing_class is TimingClass.EARLY
    assert record.mae is not None and record.mae <= -2.0
    assert record.mfe is not None and record.mfe >= 2.0
    assert "adverse" in record.classification_reason.lower()


def test_late_buy_weak_followthrough(tmp_path: Path) -> None:
    clock = FakeClock()
    auditor = EntryTimingAuditor(
        clock=clock,
        log_writer=TimingLogWriter(tmp_path / "l.jsonl"),
        id_factory=lambda: "l1",
    )
    record = _run_path(
        auditor,
        clock,
        decision=TradeDecision.BUY_INTERNAL,
        entry_price=100.0,
        path=[
            (30, 100.5),
            (60, 100.8),
            (120, 101.0),
            (180, 101.2),
            (300, 101.5),  # MFE < 3, 5m <= 2
        ],
    )
    assert record.timing_class is TimingClass.LATE
    assert record.mfe is not None and record.mfe < 3.0


def test_sell_checkpoints_and_mfe_mae(tmp_path: Path) -> None:
    clock = FakeClock()
    auditor = EntryTimingAuditor(
        clock=clock,
        log_writer=TimingLogWriter(tmp_path / "s.jsonl"),
        id_factory=lambda: "s1",
    )
    record = _run_path(
        auditor,
        clock,
        decision=TradeDecision.SELL_INTERNAL,
        entry_price=200.0,
        path=[
            (30, 199.0),
            (60, 198.0),
            (120, 197.0),
            (180, 196.0),
            (300, 195.0),
        ],
    )
    assert record.decision == "SELL_INTERNAL"
    assert record.checkpoints[-1].points == pytest.approx(5.0)
    assert record.mfe == pytest.approx(5.0)
    assert record.timing_class is TimingClass.NORMAL


def test_summary_averages(tmp_path: Path) -> None:
    clock = FakeClock()
    ids = iter(["a", "b"])
    auditor = EntryTimingAuditor(
        clock=clock,
        log_writer=TimingLogWriter(tmp_path / "sum.jsonl"),
        id_factory=lambda: next(ids),
    )
    _run_path(
        auditor,
        clock,
        decision=TradeDecision.BUY_INTERNAL,
        entry_price=100.0,
        path=[(30, 101), (60, 102), (120, 103), (180, 104), (300, 105)],
    )
    # Reset edge so second BUY_INTERNAL opens.
    auditor.observe(
        _decision(TradeDecision.NO_TRADE, timestamp=clock.now + 1),
        current_price=105.0,
        timestamp=clock.now + 1,
    )
    _run_path(
        auditor,
        clock,
        decision=TradeDecision.BUY_INTERNAL,
        entry_price=100.0,
        path=[(30, 100.2), (60, 100.4), (120, 100.6), (180, 100.8), (300, 101.0)],
    )
    summary = auditor.summary()
    assert summary.signal_count == 2
    assert summary.average_mfe > 0
    assert summary.average_points_5m > 0
    report = auditor.format_report()
    assert "PERFORMANCE SUMMARY" in report
    assert "Signal" in report


def test_classify_timing_rules_unit() -> None:
    early_cls, _ = classify_timing(
        mfe=5.0,
        mae=-3.0,
        checkpoints=(CheckpointSample(300, 110.0, 4.0),),
    )
    assert early_cls is TimingClass.EARLY

    late_cls, _ = classify_timing(
        mfe=1.5,
        mae=-0.5,
        checkpoints=(CheckpointSample(300, 101.0, 1.0),),
    )
    assert late_cls is TimingClass.LATE

    normal_cls, _ = classify_timing(
        mfe=10.0,
        mae=-1.0,
        checkpoints=(CheckpointSample(300, 110.0, 8.0),),
    )
    assert normal_cls is TimingClass.NORMAL
