"""Market Memory Diagnostics models (Sprint 43) — read-only views."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.memory.memory_types import MemorySource


class MemoryBandName(StrEnum):
    """Observation band labels (diagnostic windows, not trading thresholds)."""

    FAST = "FAST"
    MEDIUM = "MEDIUM"
    SLOW = "SLOW"


class ConsensusStatus(StrEnum):
    """Cross-band consensus status for diagnostics display."""

    ALIGNED = "ALIGNED"
    MIXED = "MIXED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class BandSummary:
    """One observation band summary (Direction / Strength / Confidence / Persistence)."""

    name: MemoryBandName
    window_seconds: float
    direction: str
    buy_count: int
    sell_count: int
    neutral_count: int
    strength: float  # 0–100
    confidence: float  # 0–100
    persistence: float  # 0–100
    record_count: int


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """Per-source diagnostics row."""

    source: MemorySource
    current_direction: str
    average_strength: float  # 0–100
    average_confidence: float  # 0–100
    record_count: int
    last_update: float | None


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """One recent memory event for the diagnostics timeline."""

    timestamp: float
    source: MemorySource
    direction: str
    strength: float  # 0–100 display
    confidence: float  # 0–100 display


@dataclass(frozen=True, slots=True)
class ConsensusSummary:
    """Cross-band consensus diagnostics."""

    direction: str
    confidence: float  # 0–100
    agreement: float  # 0–100
    status: ConsensusStatus
    fast_direction: str
    medium_direction: str
    slow_direction: str


@dataclass(frozen=True, slots=True)
class StoreDiagnosticsSummary:
    """Store-level diagnostics (size, ring usage, rates)."""

    memory_size: int
    capacity: int
    ring_buffer_usage: float  # 0–100 percent
    oldest_record: float | None
    newest_record: float | None
    records_per_source: dict[MemorySource, int]
    average_append_rate: float | None  # records / second over buffer span


@dataclass(frozen=True, slots=True)
class MemoryDiagnosticsReport:
    """Full read-only Market Memory diagnostics snapshot (Sprint 43).

    Never written to Memory. Never consumed by Trade Decision.
    """

    bands: tuple[BandSummary, BandSummary, BandSummary]
    sources: tuple[SourceSummary, ...]
    consensus: ConsensusSummary
    timeline: tuple[TimelineEvent, ...]
    store: StoreDiagnosticsSummary
    as_of: float
