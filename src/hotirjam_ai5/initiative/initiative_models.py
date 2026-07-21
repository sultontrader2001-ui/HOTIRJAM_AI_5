"""Initiative Engine input / intermediate models — observation only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.objective import ObjectiveSnapshot


class ImpulseSide(StrEnum):
    """Internal directional impulse label for detectors (not a trade decision)."""

    BUYER = "BUYER"
    SELLER = "SELLER"
    NONE = "NONE"


class MomentumState(StrEnum):
    """Coarse momentum intensity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class InitiativeSide(StrEnum):
    """Auction-control dominant side. Never a trade instruction."""

    BUYER = "BUYER"
    SELLER = "SELLER"
    NONE = "NONE"


class InitiativeState(StrEnum):
    """H-5 Initiative lifecycle."""

    NONE = "NONE"
    EMERGING = "EMERGING"
    DOMINANT = "DOMINANT"
    WEAKENING = "WEAKENING"
    EXPIRED = "EXPIRED"


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
    """Read-only inputs for one Initiative Engine evaluation.

    ``objectives`` is optional context only. It must never choose Dominant Side.
    """

    candles: tuple[OhlcCandle, ...]
    tick_size: float
    timestamp: float
    objectives: ObjectiveSnapshot | None = None


@dataclass(frozen=True, slots=True)
class ImpulseResult:
    """Force / impulse channel."""

    side: ImpulseSide
    score: float  # 0-100
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MomentumResult:
    """Motion / momentum channel."""

    score: float  # 0-100
    state: MomentumState
    direction: ImpulseSide
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandleStrengthResult:
    """Pressure / candle-body channel."""

    score: float  # 0-100
    direction: ImpulseSide
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InitiativeEvidence:
    """Structured independent evidence channels (0–100 each)."""

    force: float
    motion: float
    pressure: float
    liquidity: float
    energy: float
    context: float

    def summary_lines(self) -> tuple[str, ...]:
        return (
            f"Force {self.force:.1f}",
            f"Motion {self.motion:.1f}",
            f"Pressure {self.pressure:.1f}",
            f"Liquidity {self.liquidity:.1f}",
            f"Energy {self.energy:.1f}",
            f"Context {self.context:.1f}",
        )
