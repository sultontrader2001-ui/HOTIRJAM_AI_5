"""Position Lock models — one ACTIVE trade at a time (Sprint 50)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping


class PositionState(StrEnum):
    """Internal lock state machine."""

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class PositionDisplayStatus(StrEnum):
    """Dashboard POSITION STATUS values."""

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


class SignalGate(StrEnum):
    """Whether new Trade Plans may be created."""

    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class BlockedSignalRecord:
    """One INTERNAL signal ignored because a position was already ACTIVE."""

    timestamp: float
    direction: str
    reason: str
    active_trade_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> BlockedSignalRecord:
        return cls(
            timestamp=float(raw["timestamp"]),
            direction=str(raw["direction"]),
            reason=str(raw["reason"]),
            active_trade_id=str(raw["active_trade_id"]),
        )


@dataclass(frozen=True, slots=True)
class PositionLockSnapshot:
    """Immutable snapshot for dashboard + diagnostics."""

    state: PositionState
    display_status: PositionDisplayStatus
    new_signals: SignalGate
    active_trade_id: str | None = None
    direction: str | None = None
    entry: float | None = None
    current_pnl: float | None = None
    duration_seconds: float | None = None
    distance_to_sl: float | None = None
    distance_to_tp: float | None = None
    blocked_signals: int = 0
    blocked_buy: int = 0
    blocked_sell: int = 0
    average_active_duration: float | None = None
