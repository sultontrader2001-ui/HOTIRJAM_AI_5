"""Tests for Sprint 46 lifetime / today performance persistence."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.dashboard.lifetime_stats import (
    LifetimeStatsStore,
    PersistedSignal,
    trading_day_ny,
)
from hotirjam_ai5.dashboard.renderer import DashboardRenderer, MISSING
from hotirjam_ai5.dashboard.models import (
    DashboardState,
    PeriodStatsView,
    SignalHistoryRowView,
)
from hotirjam_ai5.performance.models import (
    LiquidityEvidence,
    MultiZoneTimestamp,
    PhysicsEvidence,
    SignalRecord,
    SignalResult,
)
from hotirjam_ai5.performance.tracker import PerformanceTracker
from hotirjam_ai5.performance.timezones import format_multi_zone


def _ts(epoch: float) -> MultiZoneTimestamp:
    return format_multi_zone(epoch)


def _completed_record(
    *,
    signal_id: str,
    decision: str,
    entry_epoch: float,
    exit_epoch: float,
    entry: float,
    exit_price: float,
    points: float,
    result: SignalResult,
) -> SignalRecord:
    return SignalRecord(
        signal_id=signal_id,
        symbol="MNQ",
        decision=decision,
        entry_price=entry,
        buy_score=80,
        sell_score=20,
        buy_confidence=80,
        sell_confidence=20,
        market_state="TRENDING",
        behavior="STABLE",
        physics=PhysicsEvidence(velocity=1.0, acceleration=0.1),
        liquidity=LiquidityEvidence(shift="BUY", imbalance="BUY"),
        entry_time=_ts(entry_epoch),
        result=result,
        exit_price=exit_price,
        points=points,
        evaluation_time=_ts(exit_epoch),
    )


def test_empty_store_renders_double_dash(tmp_path: Path) -> None:
    store = LifetimeStatsStore(tmp_path / "stats.json")
    views = store.build_views(now_epoch=1_721_563_200.0)  # 2024-07-21 NY-ish
    assert views.today.signals is None
    assert views.lifetime.win_rate is None
    assert views.history == ()

    text = DashboardRenderer().render(
        DashboardState(
            today_stats=PeriodStatsView(),
            lifetime_stats=PeriodStatsView(),
            signal_history=(),
        )
    )
    assert "TODAY" in text
    assert "LIFETIME" in text
    assert "SIGNAL HISTORY" in text
    assert f"Win Rate{' ' * (22 - 8)}: {MISSING}" in text or "Win Rate" in text
    assert MISSING in text


def test_persist_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "lifetime_performance.json"
    store = LifetimeStatsStore(path)
    tracker = PerformanceTracker(evaluation_delay_seconds=1.0, clock=lambda: 1000.0)
    # Inject a completed record directly onto tracker internals for sync.
    record = _completed_record(
        signal_id="sig-1",
        decision="BUY_INTERNAL",
        entry_epoch=1000.0,
        exit_epoch=1300.0,
        entry=100.0,
        exit_price=101.5,
        points=1.5,
        result=SignalResult.SUCCESS,
    )
    tracker._records = [record]  # noqa: SLF001 — test harness
    store.note_open("sig-1", "HELPED")
    store.sync_completed(tracker)
    store.flush()

    reloaded = LifetimeStatsStore(path)
    views = reloaded.build_views(now_epoch=1300.0)
    assert views.lifetime.signals == 1
    assert views.lifetime.wins == 1
    assert views.lifetime.memory_helped == 1
    assert views.lifetime.average_win == 1.5
    assert len(views.history) == 1
    assert views.history[0].memory_effect == "HELPED"
    assert views.history[0].result == "WIN"


def test_today_filters_by_ny_trading_day(tmp_path: Path) -> None:
    path = tmp_path / "stats.json"
    store = LifetimeStatsStore(path)
    # Explicitly plant signals on two NY days.
    day_a = "2026-07-20"
    day_b = "2026-07-21"
    store._signals = [  # noqa: SLF001
        PersistedSignal(
            signal_id="a",
            trading_day=day_a,
            direction="BUY",
            entry_time_epoch=1.0,
            exit_time_epoch=2.0,
            entry_price=1.0,
            exit_price=2.0,
            result="WIN",
            points=1.0,
            duration_seconds=1.0,
            memory_effect="NO_EFFECT",
        ),
        PersistedSignal(
            signal_id="b",
            trading_day=day_b,
            direction="SELL",
            entry_time_epoch=3.0,
            exit_time_epoch=4.0,
            entry_price=2.0,
            exit_price=1.0,
            result="LOSS",
            points=-1.0,
            duration_seconds=1.0,
            memory_effect="HURT",
        ),
    ]
    store._persisted_ids = {"a", "b"}  # noqa: SLF001
    store._no_trade_by_day = {day_a: 5, day_b: 2}  # noqa: SLF001

    # Epoch for 2026-07-21 12:00 America/New_York
    now = 1_784_649_600.0
    assert trading_day_ny(now) == day_b
    views = store.build_views(now_epoch=now)
    assert views.today.signals == 1
    assert views.today.sell_signals == 1
    assert views.today.no_trade == 2
    assert views.today.losses == 1
    assert views.lifetime.signals == 2
    assert views.lifetime.no_trade == 7


def test_signal_history_latest_twenty(tmp_path: Path) -> None:
    store = LifetimeStatsStore(tmp_path / "h.json")
    store._signals = [  # noqa: SLF001
        PersistedSignal(
            signal_id=f"s{i}",
            trading_day="2026-07-21",
            direction="BUY" if i % 2 == 0 else "SELL",
            entry_time_epoch=float(1000 + i),
            exit_time_epoch=float(1100 + i),
            entry_price=100.0 + i,
            exit_price=100.5 + i,
            result="WIN",
            points=0.5,
            duration_seconds=100.0,
            memory_effect="NO_EFFECT",
        )
        for i in range(25)
    ]
    views = store.build_views(now_epoch=2000.0, history_limit=20)
    assert len(views.history) == 20
    # Newest first
    assert views.history[0].entry == 124.0
    assert views.history[0].index == 1


def test_renderer_today_lifetime_history_layout() -> None:
    state = DashboardState(
        today_stats=PeriodStatsView(
            signals=4,
            buy_signals=3,
            sell_signals=1,
            no_trade=10,
            wins=2,
            losses=1,
            breakeven=1,
            win_rate=66.7,
            average_rr=2.0,
            average_win=1.5,
            average_loss=0.75,
            profit_factor=2.0,
            average_mfe=1.2,
            average_mae=-0.4,
            memory_helped=1,
            memory_hurt=0,
            memory_no_effect=3,
        ),
        lifetime_stats=PeriodStatsView(
            signals=40,
            buy_signals=22,
            sell_signals=18,
            no_trade=100,
            wins=20,
            losses=15,
            breakeven=5,
            win_rate=57.1,
            profit_factor=1.4,
            largest_win=5.0,
            largest_loss=-3.0,
            net_points=12.5,
            gross_profit=30.0,
            gross_loss=17.5,
            average_signals_per_day=4.0,
            average_points_per_signal=0.31,
            memory_helped=8,
            memory_hurt=2,
            memory_no_effect=30,
            memory_accuracy=75.0,
        ),
        signal_history=(
            SignalHistoryRowView(
                index=1,
                time_label="10:30:00",
                direction="BUY",
                entry=28700.0,
                exit=28702.0,
                result="WIN",
                points=2.0,
                duration_label="5m 00s",
                memory_effect="HELPED",
            ),
        ),
    )
    text = DashboardRenderer().render(state)
    assert "TODAY" in text
    assert "LIFETIME" in text
    assert "SIGNAL HISTORY" in text
    assert "PERFORMANCE" not in text
    assert "LAST SIGNAL" not in text
    assert "Signals Today" in text
    assert "Total Signals" in text
    assert "Memory Accuracy" in text
    assert "HELPED" in text
    assert "Memory Usage" not in text  # trimmed SYSTEM
    assert "Append Rate" not in text
