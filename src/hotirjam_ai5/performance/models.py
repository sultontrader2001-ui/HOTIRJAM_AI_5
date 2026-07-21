"""Performance Tracker models — analytics only.

Observes Trade Decision activations. Never emits decisions, orders, or
broker actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SignalResult(StrEnum):
    """Outcome of a delayed price evaluation."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NEUTRAL = "NEUTRAL"
    PENDING = "PENDING"


@dataclass(frozen=True, slots=True)
class MultiZoneTimestamp:
    """One instant rendered in UTC, New York, and Tashkent."""

    utc: str
    new_york: str
    tashkent: str
    epoch_seconds: float


@dataclass(frozen=True, slots=True)
class PhysicsEvidence:
    """Physics snapshot stored with a signal."""

    velocity: float | None
    acceleration: float | None


@dataclass(frozen=True, slots=True)
class LiquidityEvidence:
    """Liquidity snapshot stored with a signal."""

    shift: str
    imbalance: str


@dataclass(frozen=True, slots=True)
class SignalRecord:
    """One observed BUY_INTERNAL or SELL_INTERNAL activation."""

    signal_id: str
    symbol: str
    decision: str
    entry_price: float
    buy_score: int
    sell_score: int
    buy_confidence: int
    sell_confidence: int
    market_state: str
    behavior: str
    physics: PhysicsEvidence
    liquidity: LiquidityEvidence
    entry_time: MultiZoneTimestamp
    result: SignalResult = SignalResult.PENDING
    exit_price: float | None = None
    points: float | None = None
    evaluation_time: MultiZoneTimestamp | None = None


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    """Immutable PERFORMANCE dashboard stats."""

    buy_signals: int = 0
    sell_signals: int = 0
    success_count: int = 0
    failed_count: int = 0
    neutral_count: int = 0
    pending_count: int = 0
    win_rate: float = 0.0
    average_points: float = 0.0
    last_signal_decision: str = "—"
    last_signal_utc: str = "—"
    last_signal_new_york: str = "—"
    last_signal_tashkent: str = "—"
