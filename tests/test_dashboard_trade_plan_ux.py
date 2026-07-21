"""Tests for Dashboard Trade Plan UX fix (Sprint 50.1).

The trade-plan panel must clearly separate:
- ACTIVE TRADE  (live trade context)
- LAST TRADE    (last completed trade)
- TRADE PLAN    (never traded — waiting placeholder)
"""

from __future__ import annotations

from hotirjam_ai5.dashboard.controller import _trade_plan_view
from hotirjam_ai5.dashboard.models import DashboardState, TradePlanView
from hotirjam_ai5.dashboard.renderer import DashboardRenderer
from hotirjam_ai5.trade_planning import TradeDirection, TradePlanStatus
from hotirjam_ai5.trade_planning.models import TradePlan, TradePlanResult


def _plan(
    *,
    direction: TradeDirection = TradeDirection.BUY,
    status: TradePlanStatus = TradePlanStatus.ACTIVE,
    result: TradePlanResult = TradePlanResult.NONE,
    exit_price: float | None = None,
    points: float | None = None,
    closed_at: float | None = None,
) -> TradePlan:
    return TradePlan(
        plan_id="TP-1",
        direction=direction,
        entry_price=100.0,
        stop_loss=98.0 if direction is TradeDirection.BUY else 102.0,
        take_profit=104.0 if direction is TradeDirection.BUY else 96.0,
        risk_points=2.0,
        reward_points=4.0,
        risk_reward=2.0,
        status=status,
        created_at=1_000.0,
        activated_at=1_000.0,
        closed_at=closed_at,
        exit_price=exit_price,
        result=result,
        points=points,
    )


# ---------------------------------------------------------------- mapping


def test_no_trade_maps_to_none_mode() -> None:
    view = _trade_plan_view(None)
    assert view.mode == "NONE"


def test_active_trade_maps_live_fields() -> None:
    view = _trade_plan_view(_plan(), current_price=101.5, now=1_090.0)
    assert view.mode == "ACTIVE"
    assert view.current_price == 101.5
    assert view.current_pnl == 1.5
    assert view.distance_to_sl == 3.5
    assert view.distance_to_tp == 2.5
    assert view.duration == "1m 30s"


def test_active_sell_trade_pnl_and_distances() -> None:
    view = _trade_plan_view(
        _plan(direction=TradeDirection.SELL),
        current_price=99.0,
        now=1_010.0,
    )
    assert view.current_pnl == 1.0
    assert view.distance_to_sl == 3.0
    assert view.distance_to_tp == 3.0


def test_closed_tp_trade_maps_exit_fields() -> None:
    view = _trade_plan_view(
        _plan(
            status=TradePlanStatus.CLOSED,
            result=TradePlanResult.WIN,
            exit_price=104.0,
            points=4.0,
            closed_at=1_120.0,
        )
    )
    assert view.mode == "CLOSED"
    assert view.exit_price == 104.0
    assert view.exit_reason == "TP"
    assert view.pnl == 4.0
    assert view.rr_achieved == 2.0
    assert view.duration == "2m 00s"


def test_closed_sl_trade_maps_exit_fields() -> None:
    view = _trade_plan_view(
        _plan(
            status=TradePlanStatus.CLOSED,
            result=TradePlanResult.LOSS,
            exit_price=98.0,
            points=-2.0,
            closed_at=1_060.0,
        )
    )
    assert view.mode == "CLOSED"
    assert view.exit_reason == "SL"
    assert view.pnl == -2.0
    assert view.rr_achieved == -1.0


# ---------------------------------------------------------------- rendering


def test_render_no_trade_placeholder() -> None:
    text = DashboardRenderer().render(DashboardState(), width=100)
    assert "TRADE PLAN" in text
    assert "No active trade." in text
    assert "Waiting for setup..." in text
    assert "ACTIVE TRADE" not in text
    assert "LAST TRADE" not in text


def test_render_active_trade_panel() -> None:
    state = DashboardState(
        trade_plan=TradePlanView(
            mode="ACTIVE",
            direction="BUY",
            entry=100.0,
            stop_loss=98.0,
            take_profit=104.0,
            risk=2.0,
            reward=4.0,
            risk_reward=2.0,
            status="ACTIVE",
            current_price=101.5,
            current_pnl=1.5,
            duration="1m 30s",
            distance_to_sl=3.5,
            distance_to_tp=2.5,
        )
    )
    text = DashboardRenderer().render(state, width=100)
    assert "ACTIVE TRADE" in text
    assert "Current Price" in text
    assert "Current P/L" in text
    assert "Distance to SL" in text
    assert "Distance to TP" in text
    assert "Duration" in text
    assert "LAST TRADE" not in text


def test_render_last_trade_panel() -> None:
    state = DashboardState(
        trade_plan=TradePlanView(
            mode="CLOSED",
            direction="BUY",
            entry=100.0,
            status="CLOSED",
            exit_price=104.0,
            exit_reason="TP",
            pnl=4.0,
            rr_achieved=2.0,
            duration="2m 0s",
        )
    )
    text = DashboardRenderer().render(state, width=100)
    assert "LAST TRADE" in text
    assert "Exit Reason" in text
    assert "RR Achieved" in text
    assert "CLOSED" in text
    assert "ACTIVE TRADE" not in text
    # Decision panel is independent — closed trade must not leak into it.
    assert "TRADE DECISION" in text
