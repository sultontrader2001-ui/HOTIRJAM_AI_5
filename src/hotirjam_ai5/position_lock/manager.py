"""Position Lock Manager — gates Trade Planning while a plan is ACTIVE (Sprint 50).

Does not modify Decision, Physics, Liquidity, or Memory. Does not place orders.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import time
from pathlib import Path

from hotirjam_ai5.position_lock.models import (
    BlockedSignalRecord,
    PositionDisplayStatus,
    PositionLockSnapshot,
    PositionState,
    SignalGate,
)
from hotirjam_ai5.trade_planning.models import TradeDirection, TradePlan

DEFAULT_BLOCKED_LOG_PATH = Path("logs") / "blocked_signals.jsonl"
BLOCK_REASON = "ACTIVE_POSITION"


class PositionLockManager:
    """Ensures at most one ACTIVE Trade Plan; logs blocked INTERNAL signals."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        blocked_log_path: Path | str | None = None,
    ) -> None:
        self._clock = clock or time.time
        self._log_path = (
            Path(blocked_log_path)
            if blocked_log_path is not None
            else DEFAULT_BLOCKED_LOG_PATH
        )
        self._state = PositionState.IDLE
        self._active_plan_id: str | None = None
        self._active_opened_at: float | None = None
        self._last_block_at: float | None = None
        self._blocked_signals = 0
        self._blocked_buy = 0
        self._blocked_sell = 0
        self._closed_durations: list[float] = []
        self._blocked_records: list[BlockedSignalRecord] = []

    @property
    def state(self) -> PositionState:
        return self._state

    @property
    def active_trade_id(self) -> str | None:
        return self._active_plan_id

    @property
    def blocked_signals(self) -> int:
        return self._blocked_signals

    @property
    def blocked_buy(self) -> int:
        return self._blocked_buy

    @property
    def blocked_sell(self) -> int:
        return self._blocked_sell

    @property
    def recent_blocks(self) -> tuple[BlockedSignalRecord, ...]:
        return tuple(self._blocked_records[-50:])

    def allows_new_plan(self) -> bool:
        """True only when IDLE (no ACTIVE trade)."""
        return self._state is PositionState.IDLE

    def on_plan_activated(self, plan: TradePlan, *, timestamp: float | None = None) -> None:
        """Transition IDLE → ACTIVE when a Trade Plan becomes ACTIVE."""
        now = timestamp if timestamp is not None else self._clock()
        self._state = PositionState.ACTIVE
        self._active_plan_id = plan.plan_id
        self._active_opened_at = (
            plan.activated_at if plan.activated_at is not None else now
        )
        self._last_block_at = None

    def on_plan_closed(self, plan: TradePlan, *, timestamp: float | None = None) -> None:
        """ACTIVE → CLOSED → IDLE after TP/SL completion."""
        now = timestamp if timestamp is not None else self._clock()
        opened = self._active_opened_at
        if opened is None and plan.activated_at is not None:
            opened = plan.activated_at
        if opened is None:
            opened = plan.created_at
        duration = max(0.0, (plan.closed_at or now) - opened)
        self._closed_durations.append(duration)
        self._state = PositionState.CLOSED
        self._active_plan_id = None
        self._active_opened_at = None
        self._last_block_at = None
        # Immediately return to IDLE so the next INTERNAL may plan.
        self._state = PositionState.IDLE

    def record_blocked(
        self,
        *,
        direction: str,
        active_trade_id: str,
        timestamp: float | None = None,
    ) -> BlockedSignalRecord:
        """Log a blocked BUY_INTERNAL / SELL_INTERNAL while ACTIVE."""
        now = timestamp if timestamp is not None else self._clock()
        record = BlockedSignalRecord(
            timestamp=now,
            direction=direction,
            reason=BLOCK_REASON,
            active_trade_id=active_trade_id,
        )
        self._blocked_signals += 1
        if direction.upper().startswith("BUY"):
            self._blocked_buy += 1
        elif direction.upper().startswith("SELL"):
            self._blocked_sell += 1
        self._blocked_records.append(record)
        if len(self._blocked_records) > 500:
            self._blocked_records = self._blocked_records[-500:]
        self._last_block_at = now
        self._append_log(record)
        return record

    def snapshot(
        self,
        *,
        plan: TradePlan | None,
        current_price: float | None,
        now: float | None = None,
    ) -> PositionLockSnapshot:
        """Build dashboard fields for POSITION STATUS."""
        instant = now if now is not None else self._clock()
        avg_duration = None
        if self._closed_durations:
            avg_duration = sum(self._closed_durations) / len(self._closed_durations)

        if self._state is PositionState.IDLE:
            return PositionLockSnapshot(
                state=PositionState.IDLE,
                display_status=PositionDisplayStatus.IDLE,
                new_signals=SignalGate.ALLOWED,
                blocked_signals=self._blocked_signals,
                blocked_buy=self._blocked_buy,
                blocked_sell=self._blocked_sell,
                average_active_duration=avg_duration,
            )

        # ACTIVE (or CLOSED mid-transition — treated as ACTIVE until released)
        display = PositionDisplayStatus.ACTIVE
        if self._last_block_at is not None:
            display = PositionDisplayStatus.BLOCKED

        direction = None
        entry = None
        current_pnl = None
        duration = None
        dist_sl = None
        dist_tp = None
        trade_id = self._active_plan_id

        if plan is not None:
            direction = plan.direction.value
            entry = plan.entry_price
            trade_id = plan.plan_id
            opened = plan.activated_at or plan.created_at
            duration = max(0.0, instant - opened)
            if current_price is not None:
                if plan.direction is TradeDirection.BUY:
                    current_pnl = current_price - plan.entry_price
                    dist_sl = current_price - plan.stop_loss
                    dist_tp = plan.take_profit - current_price
                else:
                    current_pnl = plan.entry_price - current_price
                    dist_sl = plan.stop_loss - current_price
                    dist_tp = current_price - plan.take_profit

        return PositionLockSnapshot(
            state=PositionState.ACTIVE,
            display_status=display,
            new_signals=SignalGate.BLOCKED,
            active_trade_id=trade_id,
            direction=direction,
            entry=entry,
            current_pnl=current_pnl,
            duration_seconds=duration,
            distance_to_sl=dist_sl,
            distance_to_tp=dist_tp,
            blocked_signals=self._blocked_signals,
            blocked_buy=self._blocked_buy,
            blocked_sell=self._blocked_sell,
            average_active_duration=avg_duration,
        )

    def _append_log(self, record: BlockedSignalRecord) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
