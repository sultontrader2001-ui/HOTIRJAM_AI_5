"""Initiative Engine input / intermediate models — observation only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.objective import ObjectiveSnapshot


class ImpulseSide(StrEnum):
    """Directional impulse label (NOT a trade decision)."""

    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class MomentumState(StrEnum):
    """Coarse momentum intensity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class InitiativeSide(StrEnum):
    """Which side currently holds initiative (NOT a trade decision)."""

    BUYER = "BUYER"
    SELLER = "SELLER"
    NONE = "NONE"


class InitiativeState(StrEnum):
    """Overall initiative intensity."""

    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


@dataclass(frozen=True, slots=True)
class OhlcCandle:
    """One OHLC bar with volume. Pure market data — no indicators."""

    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timestamp: float | None = None


@dataclass(frozen=True, slots=True)
class InitiativeInputs:
    """Read-only inputs for one Initiative Engine evaluation."""

    objectives: ObjectiveSnapshot
    candles: tuple[OhlcCandle, ...]
    tick_size: float
    timestamp: float


@dataclass(frozen=True, slots=True)
class ImpulseResult:
    """IN01 output."""

    side: ImpulseSide
    score: float  # 0-100
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MomentumResult:
    """IN02 output."""

    score: float  # 0-100
    state: MomentumState
    direction: ImpulseSide
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandleStrengthResult:
    """IN03 output."""

    score: float  # 0-100
    direction: ImpulseSide
    reasons: tuple[str, ...]
