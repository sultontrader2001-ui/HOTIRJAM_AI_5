"""Entry Timing Audit models — analytics only (Sprint 37).

Observes BUY_INTERNAL / SELL_INTERNAL. Never modifies Trade Decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TimingClass(StrEnum):
    """Entry timing classification for the first 5 minutes after a signal."""

    EARLY = "EARLY"
    NORMAL = "NORMAL"
    LATE = "LATE"
    INCONCLUSIVE = "INCONCLUSIVE"
    PENDING = "PENDING"


# Checkpoint offsets in seconds after entry.
CHECKPOINT_SECONDS: tuple[int, ...] = (30, 60, 120, 180, 300)
TIMING_WINDOW_SECONDS: float = 300.0


@dataclass(frozen=True, slots=True)
class CheckpointSample:
    """Price and signed points at one post-entry checkpoint."""

    offset_seconds: int
    price: float
    points: float


@dataclass(frozen=True, slots=True)
class TimingRecord:
    """Completed (or pending) entry-timing audit for one internal signal."""

    signal_id: str
    symbol: str
    decision: str
    entry_price: float
    entry_time: float
    checkpoints: tuple[CheckpointSample, ...] = ()
    mfe: float | None = None
    mae: float | None = None
    timing_class: TimingClass = TimingClass.PENDING
    classification_reason: str = "Awaiting 5-minute price path."
    exit_price: float | None = None
    exit_time: float | None = None


@dataclass(frozen=True, slots=True)
class TimingSummary:
    """Aggregate MFE/MAE and checkpoint averages across completed audits."""

    signal_count: int = 0
    early_count: int = 0
    normal_count: int = 0
    late_count: int = 0
    inconclusive_count: int = 0
    average_mfe: float = 0.0
    average_mae: float = 0.0
    average_points_30s: float = 0.0
    average_points_1m: float = 0.0
    average_points_2m: float = 0.0
    average_points_3m: float = 0.0
    average_points_5m: float = 0.0


@dataclass
class _OpenTimingPath:
    """Mutable path state while the 5-minute window is open."""

    signal_id: str
    symbol: str
    decision: str
    entry_price: float
    entry_time: float
    samples: list[tuple[float, float]] = field(default_factory=list)
    # (timestamp, price)
    captured_offsets: set[int] = field(default_factory=set)
    checkpoints: list[CheckpointSample] = field(default_factory=list)
    mfe: float = 0.0
    mae: float = 0.0
