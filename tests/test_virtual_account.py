"""Tests for Sprint 47 virtual 50K prop account."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.dashboard.lifetime_stats import PersistedSignal
from hotirjam_ai5.dashboard.models import AccountStatusView, DashboardState
from hotirjam_ai5.dashboard.renderer import DashboardRenderer, MISSING
from hotirjam_ai5.dashboard.virtual_account import (
    VirtualAccountConfig,
    VirtualAccountStore,
)


def _signal(
    *,
    signal_id: str,
    day: str,
    points: float,
    result: str,
    entry_epoch: float,
    duration: float = 300.0,
) -> PersistedSignal:
    return PersistedSignal(
        signal_id=signal_id,
        trading_day=day,
        direction="BUY",
        entry_time_epoch=entry_epoch,
        exit_time_epoch=entry_epoch + duration,
        entry_price=100.0,
        exit_price=100.0 + points,
        result=result,
        points=points,
        duration_seconds=duration,
        memory_effect="NO_EFFECT",
    )


def test_empty_account_shows_starting_balance(tmp_path: Path) -> None:
    store = VirtualAccountStore(tmp_path / "acct.json")
    snap = store.build_snapshot(now_epoch=1_784_649_600.0)
    assert snap.starting_balance == 50_000.0
    assert snap.current_balance == 50_000.0
    assert snap.current_equity == 50_000.0
    assert snap.risk_status == "SAFE"
    assert snap.lifetime_pnl is None
    assert snap.total_trades == 0


def test_points_convert_to_usd_and_persist(tmp_path: Path) -> None:
    path = tmp_path / "virtual_account.json"
    config = VirtualAccountConfig(
        starting_balance=50_000.0,
        point_value_usd=2.0,
        contracts=1,
        profit_target=3_000.0,
        max_drawdown=2_000.0,
    )
    store = VirtualAccountStore(path, config=config)
    # +10 points → +$20; -5 points → -$10
    store.sync_from_signals(
        [
            _signal(
                signal_id="w1",
                day="2026-07-21",
                points=10.0,
                result="WIN",
                entry_epoch=1_784_649_600.0,
            ),
            _signal(
                signal_id="l1",
                day="2026-07-21",
                points=-5.0,
                result="LOSS",
                entry_epoch=1_784_650_000.0,
            ),
        ]
    )
    store.flush()

    snap = store.build_snapshot(now_epoch=1_784_650_100.0)
    assert snap.lifetime_pnl == 10.0  # 20 - 10
    assert snap.current_balance == 50_010.0
    assert snap.current_equity == 50_010.0
    assert snap.total_trades == 2
    assert snap.winning_trades == 1
    assert snap.losing_trades == 1
    assert snap.win_rate == 50.0
    assert snap.gross_profit == 20.0
    assert snap.gross_loss == 10.0
    assert snap.profit_factor == 2.0
    assert snap.today_pnl == 10.0
    assert snap.today_trades == 2
    assert snap.average_hold_time_seconds == 300.0

    reloaded = VirtualAccountStore(path)
    again = reloaded.build_snapshot(now_epoch=1_784_650_100.0)
    assert again.current_balance == 50_010.0
    assert again.total_trades == 2
    assert len(reloaded.trades) == 2


def test_drawdown_and_risk_status(tmp_path: Path) -> None:
    config = VirtualAccountConfig(max_drawdown=100.0, profit_target=1_000.0)
    store = VirtualAccountStore(tmp_path / "dd.json", config=config)
    # Win then large loss → drawdown from peak
    store.sync_from_signals(
        [
            _signal(
                signal_id="a",
                day="2026-07-21",
                points=25.0,  # +$50
                result="WIN",
                entry_epoch=1000.0,
            ),
            _signal(
                signal_id="b",
                day="2026-07-21",
                points=-40.0,  # -$80 → equity 49970, peak was 50050, dd=80
                result="LOSS",
                entry_epoch=2000.0,
            ),
        ]
    )
    snap = store.build_snapshot(now_epoch=2100.0)
    assert snap.maximum_drawdown == 80.0
    assert snap.current_drawdown == 80.0
    assert snap.remaining_buffer == 20.0
    assert snap.risk_status == "DANGER"  # 80/100 >= 0.8


def test_profit_target_progress(tmp_path: Path) -> None:
    config = VirtualAccountConfig(profit_target=100.0, point_value_usd=2.0)
    store = VirtualAccountStore(tmp_path / "pt.json", config=config)
    store.sync_from_signals(
        [
            _signal(
                signal_id="p1",
                day="2026-07-21",
                points=25.0,  # $50
                result="WIN",
                entry_epoch=1000.0,
            )
        ]
    )
    snap = store.build_snapshot(now_epoch=1100.0)
    assert snap.current_progress == 50.0
    assert snap.remaining_profit == 50.0
    assert snap.progress_pct == 50.0


def test_never_duplicates_trades(tmp_path: Path) -> None:
    store = VirtualAccountStore(tmp_path / "dup.json")
    signals = [
        _signal(
            signal_id="same",
            day="2026-07-21",
            points=1.0,
            result="WIN",
            entry_epoch=1000.0,
        )
    ]
    store.sync_from_signals(signals)
    store.sync_from_signals(signals)
    assert len(store.trades) == 1


def test_account_status_section_renders() -> None:
    state = DashboardState(
        account_status=AccountStatusView(
            starting_balance=50_000.0,
            current_balance=50_120.0,
            current_equity=50_120.0,
            today_pnl=40.0,
            lifetime_pnl=120.0,
            profit_target=3_000.0,
            progress_pct=4.0,
            remaining_profit=2_880.0,
            risk_status="SAFE",
            win_rate=60.0,
            profit_factor=1.5,
        )
    )
    text = DashboardRenderer().render(state)
    assert "ACCOUNT STATUS" in text
    assert "Starting Balance      : $50,000.00" in text
    assert "Current Balance       : $50,120.00" in text
    assert "Today's P/L           : $+40.00" in text
    assert "Risk Status           : SAFE" in text
    assert "Progress %            : 4.0%" in text


def test_empty_account_panel_uses_missing() -> None:
    text = DashboardRenderer().render(DashboardState())
    assert "ACCOUNT STATUS" in text
    assert f"Risk Status           : {MISSING}" in text
