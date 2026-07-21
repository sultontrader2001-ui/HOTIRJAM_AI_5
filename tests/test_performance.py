"""Tests for Performance Tracker (Sprint 32) — analytics only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hotirjam_ai5.liquidity import LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.performance import (
    PerformanceLogWriter,
    PerformanceTracker,
    SignalResult,
    format_multi_zone,
)
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _context(*, state: str = "TRENDING", behavior: str = "TRENDING") -> MarketContextSnapshot:
    return MarketContextSnapshot(
        timestamp=1.0,
        state=state,
        state_reason="test",
        transition="NONE",
        transition_changed=False,
        transition_duration=0.0,
        behavior=behavior,
        behavior_reason="test",
        feed_status="HEALTHY",
        feed_quality="GOOD",
        dom_status="HEALTHY",
        dom_quality="GOOD",
        tick_rate=10.0,
        spread=0.25,
        summary="test context",
    )


def _physics(*, velocity: float = 1.0, acceleration: float = 0.5) -> PhysicsSnapshot:
    return PhysicsSnapshot(
        spread=0.25,
        mid_price=20100.0,
        tick_velocity=velocity,
        tick_acceleration=acceleration,
        tick_count=10,
    )


def _liquidity(*, shift: str = "BUY", imbalance: str = "BUY") -> LiquiditySnapshot:
    return LiquiditySnapshot(
        timestamp=1.0,
        liquidity_shift=shift,
        dom_imbalance=imbalance,
        confidence=0.9,
    )


def _decision(
    decision: TradeDecision,
    *,
    timestamp: float,
    buy_score: int = 90,
    sell_score: int = 10,
    buy_confidence: int = 90,
    sell_confidence: int = 10,
) -> TradeDecisionSnapshot:
    return TradeDecisionSnapshot(
        timestamp=timestamp,
        decision=decision,
        reason="test",
        next_action="Execution Engine",
        buy_score=buy_score,
        sell_score=sell_score,
        buy_confidence=buy_confidence,
        sell_confidence=sell_confidence,
    )


def test_timezone_conversion_includes_utc_ny_tashkent() -> None:
    # 2026-07-21 14:37:15 UTC
    stamp = format_multi_zone(1_784_644_635.0)
    assert stamp.utc == "2026-07-21 14:37:15"
    assert stamp.new_york.startswith("2026-07-21 10:37:15 ")
    assert "EDT" in stamp.new_york or "EST" in stamp.new_york
    assert stamp.tashkent == "2026-07-21 19:37:15 UZT"


def test_buy_evaluation_success_after_delay(tmp_path: Path) -> None:
    clock = FakeClock(1_000.0)
    tracker = PerformanceTracker(
        evaluation_delay_seconds=300.0,
        log_writer=PerformanceLogWriter(tmp_path / "performance_log.jsonl"),
        clock=clock,
        id_factory=lambda: "buy-1",
    )
    recorded = tracker.observe(
        _decision(TradeDecision.BUY_INTERNAL, timestamp=1_000.0),
        symbol="MNQ",
        current_price=100.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=_liquidity(),
        timestamp=1_000.0,
    )
    assert recorded is not None
    assert recorded.result is SignalResult.PENDING
    assert recorded.entry_time.utc
    assert recorded.entry_time.new_york
    assert recorded.entry_time.tashkent.endswith("UZT")

    clock.now = 1_299.0
    assert tracker.evaluate_pending(current_price=105.0, timestamp=1_299.0) == []

    clock.now = 1_300.0
    completed = tracker.evaluate_pending(current_price=105.0, timestamp=1_300.0)
    assert len(completed) == 1
    assert completed[0].result is SignalResult.SUCCESS
    assert completed[0].points == 5.0
    assert completed[0].exit_price == 105.0
    assert completed[0].evaluation_time is not None
    assert completed[0].evaluation_time.tashkent.endswith("UZT")


def test_sell_evaluation_success_and_failed(tmp_path: Path) -> None:
    clock = FakeClock(2_000.0)
    tracker = PerformanceTracker(
        evaluation_delay_seconds=300.0,
        log_writer=PerformanceLogWriter(tmp_path / "perf.jsonl"),
        clock=clock,
        id_factory=lambda: "sell-1",
    )
    tracker.observe(
        _decision(
            TradeDecision.SELL_INTERNAL,
            timestamp=2_000.0,
            buy_score=10,
            sell_score=92,
            buy_confidence=10,
            sell_confidence=91,
        ),
        symbol="MNQ",
        current_price=200.0,
        market_context=_context(state="VOLATILE", behavior="AGGRESSIVE"),
        physics=_physics(velocity=-1.0, acceleration=-0.4),
        liquidity=_liquidity(shift="SELL", imbalance="SELL"),
        timestamp=2_000.0,
    )
    clock.now = 2_300.0
    done = tracker.evaluate_pending(current_price=195.0, timestamp=2_300.0)
    assert done[0].result is SignalResult.SUCCESS
    assert done[0].points == 5.0

    tracker2 = PerformanceTracker(
        evaluation_delay_seconds=300.0,
        log_writer=PerformanceLogWriter(tmp_path / "perf2.jsonl"),
        clock=FakeClock(3_000.0),
        id_factory=lambda: "sell-2",
    )
    tracker2.observe(
        _decision(TradeDecision.SELL_INTERNAL, timestamp=3_000.0),
        symbol="MNQ",
        current_price=200.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=_liquidity(shift="SELL", imbalance="SELL"),
        timestamp=3_000.0,
    )
    failed = tracker2.evaluate_pending(current_price=210.0, timestamp=3_300.0)
    assert failed[0].result is SignalResult.FAILED
    assert failed[0].points == -10.0


def test_neutral_when_price_unchanged(tmp_path: Path) -> None:
    clock = FakeClock(0.0)
    tracker = PerformanceTracker(
        evaluation_delay_seconds=5.0,
        log_writer=PerformanceLogWriter(tmp_path / "n.jsonl"),
        clock=clock,
        id_factory=lambda: "n1",
    )
    tracker.observe(
        _decision(TradeDecision.BUY_INTERNAL, timestamp=0.0),
        symbol="MNQ",
        current_price=50.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=None,
        timestamp=0.0,
    )
    clock.now = 5.0
    done = tracker.evaluate_pending(current_price=50.0, timestamp=5.0)
    assert done[0].result is SignalResult.NEUTRAL
    assert done[0].points == 0.0


def test_edge_triggered_does_not_duplicate_while_ready(tmp_path: Path) -> None:
    clock = FakeClock(10.0)
    tracker = PerformanceTracker(
        evaluation_delay_seconds=300.0,
        log_writer=PerformanceLogWriter(tmp_path / "e.jsonl"),
        clock=clock,
        id_factory=lambda: "once",
    )
    args = dict(
        symbol="MNQ",
        current_price=100.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=_liquidity(),
    )
    first = tracker.observe(
        _decision(TradeDecision.BUY_INTERNAL, timestamp=10.0),
        timestamp=10.0,
        **args,
    )
    second = tracker.observe(
        _decision(TradeDecision.BUY_INTERNAL, timestamp=11.0),
        timestamp=11.0,
        **args,
    )
    assert first is not None
    assert second is None
    assert len(tracker.records) == 1


def test_jsonl_logging_of_completed_signal(tmp_path: Path) -> None:
    path = tmp_path / "performance_log.jsonl"
    clock = FakeClock(100.0)
    tracker = PerformanceTracker(
        evaluation_delay_seconds=10.0,
        log_writer=PerformanceLogWriter(path),
        clock=clock,
        id_factory=lambda: "json-1",
    )
    tracker.observe(
        _decision(TradeDecision.BUY_INTERNAL, timestamp=100.0),
        symbol="MNQ",
        current_price=10.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=_liquidity(),
        timestamp=100.0,
    )
    clock.now = 110.0
    tracker.evaluate_pending(current_price=12.0, timestamp=110.0)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["decision"] == "BUY_INTERNAL"
    assert payload["result"] == "SUCCESS"
    assert payload["entry_price"] == 10.0
    assert payload["exit_price"] == 12.0
    assert payload["points"] == 2.0
    assert "utc" in payload["entry_time"]
    assert "new_york" in payload["entry_time"]
    assert "tashkent" in payload["entry_time"]
    assert payload["evaluation_time"]["tashkent"].endswith("UZT")


def test_statistics_snapshot_win_rate_and_average(tmp_path: Path) -> None:
    clock = FakeClock(0.0)
    ids = iter(["a", "b"])
    tracker = PerformanceTracker(
        evaluation_delay_seconds=1.0,
        log_writer=PerformanceLogWriter(tmp_path / "s.jsonl"),
        clock=clock,
        id_factory=lambda: next(ids),
    )
    tracker.observe(
        _decision(TradeDecision.BUY_INTERNAL, timestamp=0.0),
        symbol="MNQ",
        current_price=100.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=_liquidity(),
        timestamp=0.0,
    )
    clock.now = 1.0
    tracker.evaluate_pending(current_price=110.0, timestamp=1.0)

    tracker.observe(
        _decision(TradeDecision.NO_TRADE, timestamp=2.0),
        symbol="MNQ",
        current_price=110.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=_liquidity(),
        timestamp=2.0,
    )
    clock.now = 3.0
    tracker.observe(
        _decision(TradeDecision.SELL_INTERNAL, timestamp=3.0),
        symbol="MNQ",
        current_price=110.0,
        market_context=_context(),
        physics=_physics(),
        liquidity=_liquidity(shift="SELL", imbalance="SELL"),
        timestamp=3.0,
    )
    clock.now = 4.0
    tracker.evaluate_pending(current_price=120.0, timestamp=4.0)

    snap = tracker.snapshot()
    assert snap.buy_signals == 1
    assert snap.sell_signals == 1
    assert snap.success_count == 1
    assert snap.failed_count == 1
    assert snap.win_rate == 50.0
    assert snap.average_points == 0.0
    assert snap.last_signal_decision == "SELL_INTERNAL"
    assert snap.last_signal_utc != "—"
    assert snap.last_signal_new_york != "—"
    assert snap.last_signal_tashkent.endswith("UZT")


def test_rejects_non_positive_delay() -> None:
    with pytest.raises(ValueError, match="evaluation_delay_seconds"):
        PerformanceTracker(evaluation_delay_seconds=0)
