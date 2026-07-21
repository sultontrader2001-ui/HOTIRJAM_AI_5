"""Virtual 50K prop account — statistics only (Sprint 47).

Converts completed HOTIRJAM observation signals into dollar P/L for a
simulated prop account. Never connects to a broker and never modifies
Decision, Physics, Liquidity, Memory, or thresholds.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from hotirjam_ai5.dashboard.lifetime_stats import PersistedSignal, trading_day_ny

NEW_YORK = ZoneInfo("America/New_York")
UTC = timezone.utc

STORE_VERSION = 1
DEFAULT_STARTING_BALANCE = 50_000.0
DEFAULT_POINT_VALUE_USD = 2.0  # MNQ: $2 per index point
DEFAULT_CONTRACTS = 1
DEFAULT_PROFIT_TARGET = 3_000.0
DEFAULT_MAX_DRAWDOWN = 2_000.0


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def trading_week_ny(epoch_seconds: float) -> str:
    """ISO week key ``YYYY-Www`` in America/New_York."""
    local = datetime.fromtimestamp(epoch_seconds, tz=UTC).astimezone(NEW_YORK)
    iso = local.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def trading_month_ny(epoch_seconds: float) -> str:
    """Calendar month ``YYYY-MM`` in America/New_York."""
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).astimezone(NEW_YORK).strftime(
        "%Y-%m"
    )


@dataclass(frozen=True, slots=True)
class VirtualAccountConfig:
    """Configurable virtual prop account parameters."""

    starting_balance: float = DEFAULT_STARTING_BALANCE
    point_value_usd: float = DEFAULT_POINT_VALUE_USD
    contracts: int = DEFAULT_CONTRACTS
    profit_target: float = DEFAULT_PROFIT_TARGET
    max_drawdown: float = DEFAULT_MAX_DRAWDOWN

    def __post_init__(self) -> None:
        if self.starting_balance <= 0:
            raise ValueError("starting_balance must be positive")
        if self.point_value_usd <= 0:
            raise ValueError("point_value_usd must be positive")
        if self.contracts <= 0:
            raise ValueError("contracts must be positive")
        if self.profit_target < 0:
            raise ValueError("profit_target must be non-negative")
        if self.max_drawdown < 0:
            raise ValueError("max_drawdown must be non-negative")

    def points_to_pnl(self, points: float) -> float:
        return points * self.point_value_usd * float(self.contracts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> VirtualAccountConfig:
        if not raw:
            return cls()
        return cls(
            starting_balance=float(raw.get("starting_balance", DEFAULT_STARTING_BALANCE)),
            point_value_usd=float(raw.get("point_value_usd", DEFAULT_POINT_VALUE_USD)),
            contracts=int(raw.get("contracts", DEFAULT_CONTRACTS)),
            profit_target=float(raw.get("profit_target", DEFAULT_PROFIT_TARGET)),
            max_drawdown=float(raw.get("max_drawdown", DEFAULT_MAX_DRAWDOWN)),
        )


@dataclass(frozen=True, slots=True)
class AccountTrade:
    """One completed virtual trade derived from an observation signal."""

    signal_id: str
    trading_day: str
    trading_week: str
    trading_month: str
    direction: str
    entry_time_epoch: float
    exit_time_epoch: float
    points: float
    pnl_usd: float
    result: str
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> AccountTrade:
        return cls(
            signal_id=str(raw["signal_id"]),
            trading_day=str(raw["trading_day"]),
            trading_week=str(raw["trading_week"]),
            trading_month=str(raw["trading_month"]),
            direction=str(raw["direction"]),
            entry_time_epoch=float(raw["entry_time_epoch"]),
            exit_time_epoch=float(raw["exit_time_epoch"]),
            points=float(raw["points"]),
            pnl_usd=float(raw["pnl_usd"]),
            result=str(raw["result"]),
            duration_seconds=float(raw["duration_seconds"]),
        )

    @classmethod
    def from_signal(cls, signal: PersistedSignal, config: VirtualAccountConfig) -> AccountTrade:
        return cls(
            signal_id=signal.signal_id,
            trading_day=signal.trading_day,
            trading_week=trading_week_ny(signal.entry_time_epoch),
            trading_month=trading_month_ny(signal.entry_time_epoch),
            direction=signal.direction,
            entry_time_epoch=signal.entry_time_epoch,
            exit_time_epoch=signal.exit_time_epoch,
            points=signal.points,
            pnl_usd=config.points_to_pnl(signal.points),
            result=signal.result,
            duration_seconds=signal.duration_seconds,
        )


@dataclass(frozen=True, slots=True)
class AccountStatusSnapshot:
    """Full virtual account snapshot (None → render as ``--`` where empty)."""

    starting_balance: float = DEFAULT_STARTING_BALANCE
    current_balance: float | None = None
    current_equity: float | None = None
    today_pnl: float | None = None
    weekly_pnl: float | None = None
    monthly_pnl: float | None = None
    lifetime_pnl: float | None = None
    gross_profit: float | None = None
    gross_loss: float | None = None
    net_profit: float | None = None
    total_trades: int | None = None
    winning_trades: int | None = None
    losing_trades: int | None = None
    win_rate: float | None = None
    average_win: float | None = None
    average_loss: float | None = None
    average_rr: float | None = None
    profit_factor: float | None = None
    largest_win: float | None = None
    largest_loss: float | None = None
    average_hold_time_seconds: float | None = None
    maximum_drawdown: float | None = None
    current_drawdown: float | None = None
    remaining_buffer: float | None = None
    risk_status: str | None = None
    profit_target: float | None = None
    current_progress: float | None = None
    remaining_profit: float | None = None
    progress_pct: float | None = None
    today_trades: int | None = None
    today_wins: int | None = None
    today_losses: int | None = None
    today_profit: float | None = None
    today_rr: float | None = None


def _risk_status(current_drawdown: float, max_drawdown: float) -> str:
    if max_drawdown <= 0:
        return "SAFE"
    ratio = current_drawdown / max_drawdown
    if ratio >= 0.8 or current_drawdown >= max_drawdown:
        return "DANGER"
    if ratio >= 0.5:
        return "WARNING"
    return "SAFE"


def _period_rr(trades: Sequence[AccountTrade]) -> float | None:
    wins = [t.pnl_usd for t in trades if t.result == "WIN"]
    losses = [abs(t.pnl_usd) for t in trades if t.result == "LOSS"]
    if not wins or not losses:
        return None
    avg_win = sum(wins) / len(wins)
    avg_loss = sum(losses) / len(losses)
    return _safe_div(avg_win, avg_loss)


def _aggregate(trades: Sequence[AccountTrade], config: VirtualAccountConfig) -> AccountStatusSnapshot:
    starting = config.starting_balance
    if not trades:
        return AccountStatusSnapshot(
            starting_balance=starting,
            current_balance=starting,
            current_equity=starting,
            today_pnl=None,
            weekly_pnl=None,
            monthly_pnl=None,
            lifetime_pnl=None,
            gross_profit=None,
            gross_loss=None,
            net_profit=None,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            profit_target=config.profit_target,
            current_progress=0.0,
            remaining_profit=config.profit_target,
            progress_pct=0.0 if config.profit_target > 0 else None,
            maximum_drawdown=0.0,
            current_drawdown=0.0,
            remaining_buffer=config.max_drawdown,
            risk_status="SAFE",
        )

    # Equity curve in exit order for drawdown.
    ordered = sorted(trades, key=lambda t: (t.exit_time_epoch, t.signal_id))
    balance = starting
    peak = starting
    max_dd = 0.0
    for trade in ordered:
        balance += trade.pnl_usd
        if balance > peak:
            peak = balance
        dd = peak - balance
        if dd > max_dd:
            max_dd = dd
    current_dd = peak - balance
    remaining_buffer = max(0.0, config.max_drawdown - current_dd)

    wins = [t for t in trades if t.result == "WIN"]
    losses = [t for t in trades if t.result == "LOSS"]
    win_pnls = [t.pnl_usd for t in wins]
    loss_pnls = [abs(t.pnl_usd) for t in losses]
    gross_profit = sum(t.pnl_usd for t in trades if t.pnl_usd > 0)
    gross_loss = abs(sum(t.pnl_usd for t in trades if t.pnl_usd < 0))
    lifetime_pnl = sum(t.pnl_usd for t in trades)
    decided = len(wins) + len(losses)
    avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else None
    avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else None
    average_rr = None
    if avg_win is not None and avg_loss is not None and avg_loss > 0:
        average_rr = avg_win / avg_loss

    progress = lifetime_pnl
    remaining_profit = (
        max(0.0, config.profit_target - progress) if config.profit_target > 0 else None
    )
    progress_pct = None
    if config.profit_target > 0:
        progress_pct = max(0.0, progress / config.profit_target * 100.0)

    return AccountStatusSnapshot(
        starting_balance=starting,
        current_balance=balance,
        current_equity=balance,
        today_pnl=None,  # filled in build_snapshot with now
        weekly_pnl=None,
        monthly_pnl=None,
        lifetime_pnl=lifetime_pnl,
        gross_profit=gross_profit if gross_profit else None,
        gross_loss=gross_loss if gross_loss else None,
        net_profit=lifetime_pnl,
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate=(len(wins) / decided * 100.0) if decided else None,
        average_win=avg_win,
        average_loss=avg_loss,
        average_rr=average_rr,
        profit_factor=_safe_div(gross_profit, gross_loss),
        largest_win=max(win_pnls) if win_pnls else None,
        largest_loss=(-max(loss_pnls)) if loss_pnls else None,
        average_hold_time_seconds=(
            sum(t.duration_seconds for t in trades) / len(trades) if trades else None
        ),
        maximum_drawdown=max_dd,
        current_drawdown=current_dd,
        remaining_buffer=remaining_buffer,
        risk_status=_risk_status(current_dd, config.max_drawdown),
        profit_target=config.profit_target,
        current_progress=progress,
        remaining_profit=remaining_profit,
        progress_pct=progress_pct,
        today_trades=None,
        today_wins=None,
        today_losses=None,
        today_profit=None,
        today_rr=None,
    )


class VirtualAccountStore:
    """Disk-backed virtual prop account driven by completed observation trades."""

    def __init__(
        self,
        path: Path | str,
        *,
        config: VirtualAccountConfig | None = None,
    ) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._config = config or VirtualAccountConfig()
        self._trades: list[AccountTrade] = []
        self._trade_ids: set[str] = set()
        self._dirty = False
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def config(self) -> VirtualAccountConfig:
        return self._config

    @property
    def trades(self) -> tuple[AccountTrade, ...]:
        with self._lock:
            return tuple(self._trades)

    def sync_from_signals(self, signals: Sequence[PersistedSignal]) -> None:
        """Append any new completed signals as virtual dollar trades."""
        with self._lock:
            changed = False
            for signal in signals:
                if signal.signal_id in self._trade_ids:
                    continue
                # Skip pure breakeven-zero if desired? Keep all completed results.
                trade = AccountTrade.from_signal(signal, self._config)
                self._trades.append(trade)
                self._trade_ids.add(trade.signal_id)
                changed = True
            if changed:
                self._dirty = True

    def flush(self) -> None:
        with self._lock:
            if self._dirty:
                self._save()
                self._dirty = False

    def build_snapshot(self, *, now_epoch: float) -> AccountStatusSnapshot:
        """Aggregate account status for ``now_epoch`` (NY day/week/month)."""
        with self._lock:
            trades = list(self._trades)
            config = self._config

        base = _aggregate(trades, config)
        if not trades:
            return base

        today = trading_day_ny(now_epoch)
        week = trading_week_ny(now_epoch)
        month = trading_month_ny(now_epoch)
        today_trades = [t for t in trades if t.trading_day == today]
        week_trades = [t for t in trades if t.trading_week == week]
        month_trades = [t for t in trades if t.trading_month == month]

        today_pnl = sum(t.pnl_usd for t in today_trades) if today_trades else None
        weekly_pnl = sum(t.pnl_usd for t in week_trades) if week_trades else None
        monthly_pnl = sum(t.pnl_usd for t in month_trades) if month_trades else None

        today_wins = sum(1 for t in today_trades if t.result == "WIN")
        today_losses = sum(1 for t in today_trades if t.result == "LOSS")

        return replace(
            base,
            today_pnl=today_pnl,
            weekly_pnl=weekly_pnl,
            monthly_pnl=monthly_pnl,
            today_trades=len(today_trades) if today_trades else (0 if base.total_trades else None),
            today_wins=today_wins if today_trades else (0 if base.total_trades else None),
            today_losses=today_losses if today_trades else (0 if base.total_trades else None),
            today_profit=today_pnl,
            today_rr=_period_rr(today_trades) if today_trades else None,
        )

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        loaded_config = VirtualAccountConfig.from_dict(raw.get("config"))
        # Preserve on-disk config (starting balance is sticky once created).
        self._config = loaded_config
        self._trades = [AccountTrade.from_dict(item) for item in raw.get("trades", [])]
        self._trade_ids = {t.signal_id for t in self._trades}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STORE_VERSION,
            "config": self._config.to_dict(),
            "trades": [t.to_dict() for t in self._trades],
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self._path)


def default_account_path(project_root: Path | None = None) -> Path:
    """Default persistence path under ``logs/virtual_account.json``."""
    root = project_root or Path.cwd()
    return root / "logs" / "virtual_account.json"
