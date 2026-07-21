"""Continuation Engine input / intermediate models — observation only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.initiative import InitiativeSnapshot, OhlcCandle
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSnapshot


class ContinuationSide(StrEnum):
    """Side whose initiative may still be continuing (NOT a trade decision)."""

    BUYER = "BUYER"
    SELLER = "SELLER"
    NONE = "NONE"


class ContinuationState(StrEnum):
    """Overall continuation intensity."""

    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


@dataclass(frozen=True, slots=True)
class ContinuationInputs:
    """Read-only inputs for one Continuation Engine evaluation."""

    objectives: ObjectiveSnapshot
    initiative: InitiativeSnapshot
    response: ResponseSnapshot
    candles: tuple[OhlcCandle, ...]
    tick_size: float
    timestamp: float


@dataclass(frozen=True, slots=True)
class PressurePersistenceResult:
    """CT01 output."""

    pressure_score: float  # 0-100
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MomentumDecayResult:
    """CT02 output. Higher score = more decay (fading momentum)."""

    momentum_decay: float  # 0-100
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContinuationStrengthResult:
    """CT03 output."""

    strength_score: float  # 0-100
    reasons: tuple[str, ...]
