"""Persistent TODAY / LIFETIME trading statistics for the dashboard (Sprint 46).

Observational aggregation only — does not change Decision, Physics, Liquidity,
Memory, or thresholds. Survives process restart via JSON on disk.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from hotirjam_ai5.entry_timing import EntryTimingAuditor
from hotirjam_ai5.performance.models import SignalRecord, SignalResult
from hotirjam_ai5.performance.tracker import PerformanceTracker

NEW_YORK = ZoneInfo("America/New_York")
UTC = timezone.utc

STORE_VERSION = 1
DEFAULT_HISTORY_LIMIT = 20
MAX_STORED_SIGNALS = 5000


def trading_day_ny(epoch_seconds: float) -> str:
    """America/New_York calendar day ``YYYY-MM-DD`` for an epoch."""
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).astimezone(NEW_YORK).strftime(
        "%Y-%m-%d"
    )


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _direction_label(decision: str) -> str:
    if decision.startswith("BUY"):
        return "BUY"
    if decision.startswith("SELL"):
        return "SELL"
    return decision.replace("_INTERNAL", "")


@dataclass(frozen=True, slots=True)
class PersistedSignal:
    """One completed observation signal retained for lifetime stats."""

    signal_id: str
    trading_day: str
    direction: str
    entry_time_epoch: float
    exit_time_epoch: float
    entry_price: float
    exit_price: float
    result: str
    points: float
    duration_seconds: float
    memory_effect: str
    mfe: float | None = None
    mae: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> PersistedSignal:
        return cls(
            signal_id=str(raw["signal_id"]),
            trading_day=str(raw["trading_day"]),
            direction=str(raw["direction"]),
            entry_time_epoch=float(raw["entry_time_epoch"]),
            exit_time_epoch=float(raw["exit_time_epoch"]),
            entry_price=float(raw["entry_price"]),
            exit_price=float(raw["exit_price"]),
            result=str(raw["result"]),
            points=float(raw["points"]),
            duration_seconds=float(raw["duration_seconds"]),
            memory_effect=str(raw.get("memory_effect", "NO_EFFECT")),
            mfe=float(raw["mfe"]) if raw.get("mfe") is not None else None,
            mae=float(raw["mae"]) if raw.get("mae") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class PeriodStatsSnapshot:
    """Aggregated metrics for TODAY or LIFETIME (None → render as ``--``)."""

    signals: int | None = None
    buy_signals: int | None = None
    sell_signals: int | None = None
    no_trade: int | None = None
    wins: int | None = None
    losses: int | None = None
    breakeven: int | None = None
    win_rate: float | None = None
    average_rr: float | None = None
    average_win: float | None = None
    average_loss: float | None = None
    profit_factor: float | None = None
    average_mfe: float | None = None
    average_mae: float | None = None
    memory_helped: int | None = None
    memory_hurt: int | None = None
    memory_no_effect: int | None = None
    # Lifetime-only extras
    largest_win: float | None = None
    largest_loss: float | None = None
    net_points: float | None = None
    gross_profit: float | None = None
    gross_loss: float | None = None
    average_signals_per_day: float | None = None
    average_points_per_signal: float | None = None
    memory_accuracy: float | None = None


@dataclass(frozen=True, slots=True)
class SignalHistoryRow:
    """One row for the SIGNAL HISTORY panel."""

    index: int
    time_label: str
    direction: str
    entry: float
    exit: float
    result: str
    points: float
    duration_label: str
    memory_effect: str


@dataclass(frozen=True, slots=True)
class LifetimeDashboardViews:
    """Views consumed by the Sprint 46 dashboard renderer."""

    today: PeriodStatsSnapshot
    lifetime: PeriodStatsSnapshot
    history: tuple[SignalHistoryRow, ...]


def _empty_period() -> PeriodStatsSnapshot:
    return PeriodStatsSnapshot()


def _map_result(result: SignalResult | str) -> str:
    text = result.value if isinstance(result, SignalResult) else str(result)
    if text == SignalResult.SUCCESS.value:
        return "WIN"
    if text == SignalResult.FAILED.value:
        return "LOSS"
    if text == SignalResult.NEUTRAL.value:
        return "BREAKEVEN"
    return text


def _format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _aggregate(
    signals: Sequence[PersistedSignal],
    *,
    no_trade: int,
    include_lifetime_extras: bool,
    pending_buy: int = 0,
    pending_sell: int = 0,
) -> PeriodStatsSnapshot:
    if not signals and no_trade == 0 and pending_buy == 0 and pending_sell == 0:
        return _empty_period()

    n_completed = len(signals)
    n = n_completed + pending_buy + pending_sell
    buys = sum(1 for s in signals if s.direction == "BUY") + pending_buy
    sells = sum(1 for s in signals if s.direction == "SELL") + pending_sell

    if n_completed == 0:
        return PeriodStatsSnapshot(
            signals=n,
            buy_signals=buys,
            sell_signals=sells,
            no_trade=no_trade,
            wins=0 if n else None,
            losses=0 if n else None,
            breakeven=0 if n else None,
            memory_helped=0 if n else None,
            memory_hurt=0 if n else None,
            memory_no_effect=0 if n else None,
        )

    wins = sum(1 for s in signals if s.result == "WIN")
    losses = sum(1 for s in signals if s.result == "LOSS")
    breakeven = sum(1 for s in signals if s.result == "BREAKEVEN")
    decided = wins + losses
    win_rate = (wins / decided * 100.0) if decided else None

    win_pts = [s.points for s in signals if s.result == "WIN"]
    loss_pts = [abs(s.points) for s in signals if s.result == "LOSS"]
    avg_win = sum(win_pts) / len(win_pts) if win_pts else None
    avg_loss = sum(loss_pts) / len(loss_pts) if loss_pts else None
    average_rr = None
    if avg_win is not None and avg_loss is not None and avg_loss > 0:
        average_rr = avg_win / avg_loss

    gross_profit = sum(s.points for s in signals if s.points > 0)
    gross_loss = abs(sum(s.points for s in signals if s.points < 0))
    profit_factor = _safe_div(gross_profit, gross_loss)

    mfes = [s.mfe for s in signals if s.mfe is not None]
    maes = [s.mae for s in signals if s.mae is not None]
    avg_mfe = sum(mfes) / len(mfes) if mfes else None
    avg_mae = sum(maes) / len(maes) if maes else None

    helped = sum(1 for s in signals if s.memory_effect == "HELPED")
    hurt = sum(1 for s in signals if s.memory_effect == "HURT")
    no_effect = sum(1 for s in signals if s.memory_effect == "NO_EFFECT")

    extras: dict[str, float | None] = {}
    if include_lifetime_extras:
        all_pts = [s.points for s in signals]
        largest_win = max((p for p in all_pts if p > 0), default=None)
        largest_loss = min((p for p in all_pts if p < 0), default=None)
        days = {s.trading_day for s in signals}
        extras = {
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "net_points": sum(all_pts),
            "gross_profit": gross_profit if gross_profit else None,
            "gross_loss": gross_loss if gross_loss else None,
            "average_signals_per_day": (n_completed / len(days)) if days else None,
            "average_points_per_signal": (sum(all_pts) / n_completed) if n_completed else None,
            "memory_accuracy": _memory_accuracy(signals),
        }

    return PeriodStatsSnapshot(
        signals=n,
        buy_signals=buys,
        sell_signals=sells,
        no_trade=no_trade,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=win_rate,
        average_rr=average_rr,
        average_win=avg_win,
        average_loss=avg_loss,
        profit_factor=profit_factor,
        average_mfe=avg_mfe,
        average_mae=avg_mae,
        memory_helped=helped,
        memory_hurt=hurt,
        memory_no_effect=no_effect,
        **extras,
    )


def _memory_accuracy(signals: Sequence[PersistedSignal]) -> float | None:
    """Share of HELPED/HURT calls that matched outcome (HELPED+WIN or HURT+LOSS)."""
    decisive = [s for s in signals if s.memory_effect in ("HELPED", "HURT")]
    if not decisive:
        return None
    correct = 0
    for signal in decisive:
        if signal.memory_effect == "HELPED" and signal.result == "WIN":
            correct += 1
        elif signal.memory_effect == "HURT" and signal.result == "LOSS":
            correct += 1
    return correct / len(decisive) * 100.0


class LifetimeStatsStore:
    """Thread-safe disk-backed store for lifetime / today performance stats."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._signals: list[PersistedSignal] = []
        self._persisted_ids: set[str] = set()
        self._no_trade_by_day: dict[str, int] = {}
        self._pending_memory: dict[str, str] = {}
        self._dirty = False
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def completed_signals(self) -> tuple[PersistedSignal, ...]:
        """All persisted completed signals (copy)."""
        with self._lock:
            return tuple(self._signals)

    def note_open(self, signal_id: str, memory_effect: str) -> None:
        """Remember Memory effect for a newly opened INTERNAL signal."""
        with self._lock:
            self._pending_memory[signal_id] = memory_effect or "NO_EFFECT"
            self._dirty = True

    def record_no_trade(self, now_epoch: float) -> None:
        """Increment NO_TRADE count for the NY trading day of ``now_epoch``."""
        day = trading_day_ny(now_epoch)
        with self._lock:
            self._no_trade_by_day[day] = self._no_trade_by_day.get(day, 0) + 1
            self._dirty = True

    def sync_completed(
        self,
        performance: PerformanceTracker,
        entry_timing: EntryTimingAuditor | None = None,
    ) -> None:
        """Persist any newly completed PerformanceTracker records."""
        timing_pool = list(entry_timing.completed) if entry_timing is not None else []
        with self._lock:
            changed = False
            for record in performance.records:
                if record.result is SignalResult.PENDING:
                    continue
                if record.exit_price is None or record.evaluation_time is None:
                    continue
                if record.points is None:
                    continue
                if record.signal_id in self._persisted_ids:
                    continue
                memory = self._pending_memory.pop(record.signal_id, "NO_EFFECT")
                mfe, mae = _match_mfe_mae(record, timing_pool)
                exit_epoch = record.evaluation_time.epoch_seconds
                entry_epoch = record.entry_time.epoch_seconds
                persisted = PersistedSignal(
                    signal_id=record.signal_id,
                    trading_day=trading_day_ny(entry_epoch),
                    direction=_direction_label(record.decision),
                    entry_time_epoch=entry_epoch,
                    exit_time_epoch=exit_epoch,
                    entry_price=record.entry_price,
                    exit_price=record.exit_price,
                    result=_map_result(record.result),
                    points=float(record.points),
                    duration_seconds=max(0.0, exit_epoch - entry_epoch),
                    memory_effect=memory,
                    mfe=mfe,
                    mae=mae,
                )
                self._signals.append(persisted)
                self._persisted_ids.add(record.signal_id)
                changed = True
            if len(self._signals) > MAX_STORED_SIGNALS:
                overflow = len(self._signals) - MAX_STORED_SIGNALS
                removed = self._signals[:overflow]
                self._signals = self._signals[overflow:]
                for item in removed:
                    self._persisted_ids.discard(item.signal_id)
                changed = True
            if changed:
                self._dirty = True

    def flush(self) -> None:
        """Write dirty state to disk."""
        with self._lock:
            if self._dirty:
                self._save()
                self._dirty = False

    def build_views(
        self,
        *,
        now_epoch: float,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
        pending_records: Sequence[SignalRecord] = (),
    ) -> LifetimeDashboardViews:
        """Build TODAY / LIFETIME / HISTORY snapshots for the renderer."""
        today = trading_day_ny(now_epoch)
        with self._lock:
            signals = list(self._signals)
            no_trade_today = self._no_trade_by_day.get(today, 0)
            no_trade_life = sum(self._no_trade_by_day.values())

        pending_buy_today = 0
        pending_sell_today = 0
        pending_buy_life = 0
        pending_sell_life = 0
        for record in pending_records:
            if record.result is not SignalResult.PENDING:
                continue
            direction = _direction_label(record.decision)
            day = trading_day_ny(record.entry_time.epoch_seconds)
            if direction == "BUY":
                pending_buy_life += 1
                if day == today:
                    pending_buy_today += 1
            elif direction == "SELL":
                pending_sell_life += 1
                if day == today:
                    pending_sell_today += 1

        today_signals = [s for s in signals if s.trading_day == today]
        has_today = (
            bool(today_signals)
            or no_trade_today > 0
            or pending_buy_today > 0
            or pending_sell_today > 0
        )
        has_life = (
            bool(signals)
            or no_trade_life > 0
            or pending_buy_life > 0
            or pending_sell_life > 0
        )

        today_view = (
            _aggregate(
                today_signals,
                no_trade=no_trade_today,
                include_lifetime_extras=False,
                pending_buy=pending_buy_today,
                pending_sell=pending_sell_today,
            )
            if has_today
            else _empty_period()
        )
        life_view = (
            _aggregate(
                signals,
                no_trade=no_trade_life,
                include_lifetime_extras=True,
                pending_buy=pending_buy_life,
                pending_sell=pending_sell_life,
            )
            if has_life
            else _empty_period()
        )

        recent = list(reversed(signals[-history_limit:]))
        history = tuple(
            SignalHistoryRow(
                index=i + 1,
                time_label=datetime.fromtimestamp(s.entry_time_epoch, tz=UTC)
                .astimezone(NEW_YORK)
                .strftime("%H:%M:%S"),
                direction=s.direction,
                entry=s.entry_price,
                exit=s.exit_price,
                result=s.result,
                points=s.points,
                duration_label=_format_duration(s.duration_seconds),
                memory_effect=s.memory_effect,
            )
            for i, s in enumerate(recent)
        )
        return LifetimeDashboardViews(today=today_view, lifetime=life_view, history=history)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        signals_raw = raw.get("signals", [])
        self._signals = [PersistedSignal.from_dict(item) for item in signals_raw]
        self._persisted_ids = {s.signal_id for s in self._signals}
        self._no_trade_by_day = {
            str(k): int(v) for k, v in dict(raw.get("no_trade_by_day", {})).items()
        }
        self._pending_memory = {
            str(k): str(v) for k, v in dict(raw.get("pending_memory", {})).items()
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STORE_VERSION,
            "signals": [s.to_dict() for s in self._signals],
            "no_trade_by_day": self._no_trade_by_day,
            "pending_memory": self._pending_memory,
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self._path)


def _match_mfe_mae(
    record: SignalRecord,
    timing_records: Sequence[Any],
) -> tuple[float | None, float | None]:
    """Best-effort attach Entry Timing MFE/MAE to a completed performance signal."""
    entry_epoch = record.entry_time.epoch_seconds
    for timing in timing_records:
        if timing.decision != record.decision:
            continue
        if abs(timing.entry_price - record.entry_price) > 1e-9:
            continue
        if abs(float(timing.entry_time) - entry_epoch) > 2.0:
            continue
        if timing.mfe is None or timing.mae is None:
            continue
        return float(timing.mfe), float(timing.mae)
    return None, None


def default_stats_path(project_root: Path | None = None) -> Path:
    """Default persistence path under ``logs/lifetime_performance.json``."""
    root = project_root or Path.cwd()
    return root / "logs" / "lifetime_performance.json"
