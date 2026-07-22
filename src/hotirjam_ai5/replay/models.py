"""Replay validation models (H-8.1). Immutable results only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModuleVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class ConfidenceLabel(StrEnum):
    CALIBRATED = "Calibrated"
    TOO_HIGH = "Too High"
    TOO_LOW = "Too Low"


@dataclass(frozen=True, slots=True)
class MarketPoint:
    """One subsequent market sample after an observation (read-only input)."""

    time: float
    price: float


@dataclass(frozen=True, slots=True)
class ObservationReplayResult:
    """Per-observation replay validation outcome."""

    cycle_id: int
    observation_time: float
    objective: ModuleVerdict
    initiative: ModuleVerdict
    response: ModuleVerdict
    continuation: ModuleVerdict
    break_capability: ModuleVerdict
    confidence: ConfidenceLabel
    notes: tuple[str, ...]
    subsequent_points: int


@dataclass(frozen=True, slots=True)
class ReplayReport:
    """Full replay session report."""

    results: tuple[ObservationReplayResult, ...]
    session_pass: bool
    summary_lines: tuple[str, ...]
    deterministic_fingerprint: str

    @property
    def verdict(self) -> str:
        return "PASS" if self.session_pass else "FAIL"
