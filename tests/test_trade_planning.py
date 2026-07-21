"""Tests for Trade Planning Engine v1 (Sprint 49)."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.dashboard.models import DashboardState, TradePlanView
from hotirjam_ai5.dashboard.renderer import DashboardRenderer
from hotirjam_ai5.dashboard.virtual_account import VirtualAccountStore
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot
from hotirjam_ai5.trade_planning import (
    TradeDirection,
    TradePlanStatus,
    TradePlanningConfig,
    TradePlanningEngine,
)
from hotirjam_ai5.trade_planning.models import TradePlanResult


def _decision(kind: TradeDecision, ts: float = 1000.0) -> TradeDecisionSnapshot:
    return TradeDecisionSnapshot(
        timestamp=ts,
        decision=kind,
        reason="test",
        next_action="none",
        buy_score=80,
        buy_confidence=80,
        sell_score=20,
        sell_confidence=20,
    )


def test_buy_planning_swing_stop_and_rr(tmp_path: Path) -> None:
    engine = TradePlanningEngine(
        config=TradePlanningConfig(default_rr=2.0, min_stop_points=2.0),
        path=tmp_path / "plans.json",
        clock=lambda: 1000.0,
        id_factory=lambda: "buy-1",
    )
    for price in (100.0, 99.0, 98.5, 99.5, 100.5):
        engine.record_price(price, velocity=1.0)

    plan = engine.observe(
        _decision(TradeDecision.BUY_INTERNAL, 1000.0),
        current_price=100.5,
        timestamp=1000.0,
        velocity=1.0,
    )
    assert plan is not None
    assert plan.direction is TradeDirection.BUY
    assert plan.status is TradePlanStatus.ACTIVE
    assert plan.stop_loss == 98.5  # swing / momentum origin low
    assert plan.entry_price == 100.5
    risk = 100.5 - 98.5
    assert plan.risk_points == risk
    assert plan.reward_points == risk * 2.0
    assert plan.take_profit == 100.5 + risk * 2.0
    assert abs(plan.risk_reward - 2.0) < 1e-9


def test_sell_planning_swing_stop_and_rr(tmp_path: Path) -> None:
    engine = TradePlanningEngine(
        config=TradePlanningConfig(default_rr=2.0),
        path=tmp_path / "plans.json",
        clock=lambda: 2000.0,
        id_factory=lambda: "sell-1",
    )
    for price in (100.0, 101.0, 102.0, 101.5, 100.0):
        engine.record_price(price, velocity=-1.0)

    plan = engine.observe(
        _decision(TradeDecision.SELL_INTERNAL, 2000.0),
        current_price=100.0,
        timestamp=2000.0,
        velocity=-1.0,
    )
    assert plan is not None
    assert plan.direction is TradeDirection.SELL
    assert plan.stop_loss == 102.0
    risk = 102.0 - 100.0
    assert plan.risk_points == risk
    assert plan.take_profit == 100.0 - risk * 2.0
    assert abs(plan.risk_reward - 2.0) < 1e-9


def test_fallback_stop_when_no_history(tmp_path: Path) -> None:
    engine = TradePlanningEngine(
        config=TradePlanningConfig(min_stop_points=3.0, default_rr=2.0),
        path=tmp_path / "plans.json",
        id_factory=lambda: "fb-1",
    )
    plan = engine.observe(
        _decision(TradeDecision.BUY_INTERNAL),
        current_price=200.0,
        timestamp=1.0,
    )
    assert plan is not None
    assert plan.stop_loss == 197.0
    assert plan.stop_source == "fallback"
    assert plan.take_profit == 200.0 + 6.0


def test_no_trade_does_not_create_plan(tmp_path: Path) -> None:
    engine = TradePlanningEngine(path=tmp_path / "plans.json")
    result = engine.observe(
        _decision(TradeDecision.NO_TRADE),
        current_price=100.0,
    )
    assert result is None
    assert engine.active_plan is None


def test_tp_closes_win_and_updates_virtual_account(tmp_path: Path) -> None:
    engine = TradePlanningEngine(
        config=TradePlanningConfig(default_rr=2.0, min_stop_points=2.0),
        path=tmp_path / "plans.json",
        id_factory=lambda: "tp-1",
    )
    engine.record_price(98.0, velocity=1.0)
    plan = engine.observe(
        _decision(TradeDecision.BUY_INTERNAL, 10.0),
        current_price=100.0,
        timestamp=10.0,
    )
    assert plan is not None
    closed = engine.update_price(current_price=plan.take_profit, timestamp=20.0)
    assert len(closed) == 1
    assert closed[0].status is TradePlanStatus.CLOSED
    assert closed[0].result is TradePlanResult.WIN
    assert closed[0].points == plan.reward_points

    account = VirtualAccountStore(tmp_path / "acct.json")
    account.sync_from_trade_plans(engine.closed_plans)
    account.flush()
    snap = account.build_snapshot(now_epoch=20.0)
    assert snap.winning_trades == 1
    assert snap.lifetime_pnl == account.config.points_to_pnl(plan.reward_points)
    assert snap.current_balance == 50_000.0 + snap.lifetime_pnl


def test_sl_closes_loss(tmp_path: Path) -> None:
    engine = TradePlanningEngine(
        config=TradePlanningConfig(min_stop_points=2.0, default_rr=2.0),
        path=tmp_path / "plans.json",
        id_factory=lambda: "sl-1",
    )
    plan = engine.observe(
        _decision(TradeDecision.BUY_INTERNAL, 10.0),
        current_price=100.0,
        timestamp=10.0,
    )
    assert plan is not None
    closed = engine.update_price(current_price=plan.stop_loss, timestamp=15.0)
    assert closed[0].result is TradePlanResult.LOSS
    assert closed[0].points == -plan.risk_points


def test_configurable_rr(tmp_path: Path) -> None:
    engine = TradePlanningEngine(
        config=TradePlanningConfig(default_rr=3.0, min_stop_points=2.0),
        path=tmp_path / "plans.json",
        id_factory=lambda: "rr-1",
    )
    plan = engine.observe(
        _decision(TradeDecision.BUY_INTERNAL),
        current_price=100.0,
    )
    assert plan is not None
    assert plan.risk_reward == 3.0
    assert plan.reward_points == 6.0


def test_trade_plan_dashboard_panel() -> None:
    state = DashboardState(
        trade_plan=TradePlanView(
            direction="BUY",
            entry=100.0,
            stop_loss=98.0,
            take_profit=104.0,
            risk=2.0,
            reward=4.0,
            risk_reward=2.0,
            status="ACTIVE",
        )
    )
    text = DashboardRenderer().render(state, width=100)
    assert "TRADE PLAN" in text
    assert "Direction" in text
    assert "Stop Loss" in text
    assert "Take Profit" in text
    assert "ACTIVE" in text
    assert "2.00" in text


def test_plans_persist_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "plans.json"
    engine = TradePlanningEngine(
        path=path,
        id_factory=lambda: "persist-1",
        config=TradePlanningConfig(min_stop_points=2.0),
    )
    engine.observe(
        _decision(TradeDecision.BUY_INTERNAL, 1.0),
        current_price=100.0,
        timestamp=1.0,
    )
    reloaded = TradePlanningEngine(path=path)
    assert reloaded.active_plan is not None
    assert reloaded.active_plan.plan_id == "persist-1"
    assert reloaded.active_plan.status is TradePlanStatus.ACTIVE
