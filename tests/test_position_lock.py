"""Tests for Position Lock Manager (Sprint 50)."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.dashboard.models import DashboardState, PositionStatusView
from hotirjam_ai5.dashboard.renderer import DashboardRenderer
from hotirjam_ai5.dashboard.virtual_account import VirtualAccountStore
from hotirjam_ai5.position_lock import (
    BLOCK_REASON,
    PositionLockManager,
    PositionState,
    SignalGate,
)
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot
from hotirjam_ai5.trade_planning import (
    TradePlanStatus,
    TradePlanningConfig,
    TradePlanningEngine,
)


def _decision(kind: TradeDecision, ts: float) -> TradeDecisionSnapshot:
    return TradeDecisionSnapshot(
        timestamp=ts,
        decision=kind,
        reason="test",
        next_action="none",
    )


def test_single_active_trade_blocks_second_buy(tmp_path: Path) -> None:
    ids = iter(["plan-a", "plan-b"])
    planning = TradePlanningEngine(
        path=tmp_path / "plans.json",
        id_factory=lambda: next(ids),
        config=TradePlanningConfig(min_stop_points=2.0),
    )
    lock = PositionLockManager(blocked_log_path=tmp_path / "blocked.jsonl")

    first = planning.observe(
        _decision(TradeDecision.BUY_INTERNAL, 1.0),
        current_price=100.0,
        timestamp=1.0,
        allow_new=True,
    )
    assert first is not None
    lock.on_plan_activated(first, timestamp=1.0)
    assert lock.state is PositionState.ACTIVE
    assert not lock.allows_new_plan()

    # Edge away then back to BUY while still ACTIVE.
    planning.observe(
        _decision(TradeDecision.NO_TRADE, 2.0),
        current_price=100.5,
        timestamp=2.0,
        allow_new=False,
    )
    second = planning.observe(
        _decision(TradeDecision.BUY_INTERNAL, 3.0),
        current_price=101.0,
        timestamp=3.0,
        allow_new=lock.allows_new_plan(),
    )
    assert second is None
    assert planning.active_plan is not None
    assert planning.active_plan.plan_id == "plan-a"
    lock.record_blocked(
        direction="BUY",
        active_trade_id="plan-a",
        timestamp=3.0,
    )
    assert lock.blocked_signals == 1
    assert lock.blocked_buy == 1
    assert lock.blocked_sell == 0
    log_text = (tmp_path / "blocked.jsonl").read_text(encoding="utf-8")
    assert BLOCK_REASON in log_text
    assert "plan-a" in log_text


def test_sell_blocked_while_active(tmp_path: Path) -> None:
    planning = TradePlanningEngine(
        path=tmp_path / "plans.json",
        id_factory=lambda: "only",
        config=TradePlanningConfig(min_stop_points=2.0),
    )
    lock = PositionLockManager(blocked_log_path=tmp_path / "b.jsonl")
    plan = planning.observe(
        _decision(TradeDecision.BUY_INTERNAL, 1.0),
        current_price=100.0,
        timestamp=1.0,
    )
    assert plan is not None
    lock.on_plan_activated(plan)
    planning.observe(
        _decision(TradeDecision.NO_TRADE, 2.0),
        current_price=100.0,
        timestamp=2.0,
        allow_new=False,
    )
    blocked = planning.observe(
        _decision(TradeDecision.SELL_INTERNAL, 3.0),
        current_price=99.0,
        timestamp=3.0,
        allow_new=False,
    )
    assert blocked is None
    lock.record_blocked(direction="SELL", active_trade_id="only", timestamp=3.0)
    assert lock.blocked_sell == 1


def test_trade_close_unlocks_position(tmp_path: Path) -> None:
    planning = TradePlanningEngine(
        path=tmp_path / "plans.json",
        id_factory=lambda: "close-1",
        config=TradePlanningConfig(min_stop_points=2.0, default_rr=2.0),
    )
    lock = PositionLockManager(blocked_log_path=tmp_path / "b.jsonl")
    plan = planning.observe(
        _decision(TradeDecision.BUY_INTERNAL, 1.0),
        current_price=100.0,
        timestamp=1.0,
    )
    assert plan is not None
    lock.on_plan_activated(plan, timestamp=1.0)
    closed = planning.update_price(current_price=plan.take_profit, timestamp=10.0)
    assert len(closed) == 1
    lock.on_plan_closed(closed[0], timestamp=10.0)
    assert lock.state is PositionState.IDLE
    assert lock.allows_new_plan()

    nxt = planning.observe(
        _decision(TradeDecision.SELL_INTERNAL, 11.0),
        current_price=100.0,
        timestamp=11.0,
        allow_new=True,
    )
    assert nxt is not None
    assert nxt.plan_id == "close-1" or nxt.status is TradePlanStatus.ACTIVE


def test_virtual_account_ignores_blocked_only_closed_affects(
    tmp_path: Path,
) -> None:
    planning = TradePlanningEngine(
        path=tmp_path / "plans.json",
        id_factory=lambda: "va-1",
        config=TradePlanningConfig(min_stop_points=2.0),
    )
    plan = planning.observe(
        _decision(TradeDecision.BUY_INTERNAL, 1.0),
        current_price=100.0,
        timestamp=1.0,
    )
    assert plan is not None
    # Blocked signal never becomes a plan — account unchanged.
    account = VirtualAccountStore(tmp_path / "acct.json")
    account.sync_from_trade_plans(planning.closed_plans)
    snap = account.build_snapshot(now_epoch=1.0)
    assert snap.total_trades == 0
    assert snap.current_balance == 50_000.0

    closed = planning.update_price(current_price=plan.take_profit, timestamp=5.0)
    account.sync_from_trade_plans(planning.closed_plans)
    snap2 = account.build_snapshot(now_epoch=5.0)
    assert snap2.winning_trades == 1
    assert len(closed) == 1


def test_position_status_snapshot_metrics(tmp_path: Path) -> None:
    planning = TradePlanningEngine(
        path=tmp_path / "plans.json",
        id_factory=lambda: "m1",
        config=TradePlanningConfig(min_stop_points=2.0, default_rr=2.0),
    )
    lock = PositionLockManager(blocked_log_path=tmp_path / "b.jsonl")
    plan = planning.observe(
        _decision(TradeDecision.BUY_INTERNAL, 100.0),
        current_price=100.0,
        timestamp=100.0,
    )
    assert plan is not None
    lock.on_plan_activated(plan, timestamp=100.0)
    snap = lock.snapshot(plan=plan, current_price=101.0, now=110.0)
    assert snap.new_signals is SignalGate.BLOCKED
    assert snap.entry == 100.0
    assert snap.current_pnl == 1.0
    assert snap.duration_seconds == 10.0
    assert snap.distance_to_sl == 101.0 - plan.stop_loss
    assert snap.distance_to_tp == plan.take_profit - 101.0


def test_position_status_dashboard_panel() -> None:
    state = DashboardState(
        position_status=PositionStatusView(
            status="ACTIVE",
            current_trade_id="abc",
            entry=100.0,
            current_pnl=1.5,
            duration="10s",
            distance_to_sl=3.0,
            distance_to_tp=2.5,
            new_signals="BLOCKED",
            blocked_signals=2,
            blocked_buy=1,
            blocked_sell=1,
            average_active_duration="5s",
        )
    )
    text = DashboardRenderer().render(state, width=100)
    assert "POSITION STATUS" in text
    assert "BLOCKED" in text
    assert "New Signals" in text
    assert "Distance to SL" in text
    assert "Current P/L" in text
