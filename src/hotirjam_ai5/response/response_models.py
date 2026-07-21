"""Response Engine input / intermediate models — observation only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.initiative import InitiativeSnapshot, OhlcCandle
from hotirjam_ai5.objective import ObjectiveSnapshot


class ResponseSide(StrEnum):
    """Which side attempted the counter-response (NOT a trade decision)."""

    BUYER = "BUYER"
    SELLER = "SELLER"
    NONE = "NONE"


class ResponseState(StrEnum):
    """Quality classification of the counter-response."""

    FAILED = "FAILED"
    WEAK = "WEAK"
    NEUTRAL = "NEUTRAL"
    STRONG = "STRONG"


@dataclass(frozen=True, slots=True)
class ResponseInputs:
    """Read-only inputs for one Response Engine evaluation."""

    objectives: ObjectiveSnapshot
    initiative: InitiativeSnapshot
    candles: tuple[OhlcCandle, ...]
    tick_size: float
    timestamp: float


@dataclass(frozen=True, slots=True)
class CounterMoveResult:
    """RE01 output."""

    detected: bool
    response_side: ResponseSide
    magnitude_ticks: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResponseStrengthResult:
    """RE02 output."""

    strength: float  # 0-100
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InitiativePreservationResult:
    """RE03 output."""

    preserved: bool
    reasons: tuple[str, ...]
