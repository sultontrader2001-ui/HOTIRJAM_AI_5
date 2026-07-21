"""Break Capability Engine input / intermediate models — observation only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.continuation import ContinuationSnapshot
from hotirjam_ai5.initiative import InitiativeSnapshot
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSnapshot


class TargetSide(StrEnum):
    """Side applying pressure toward an objective (NOT a trade decision)."""

    BUYER = "BUYER"
    SELLER = "SELLER"
    NONE = "NONE"


class TargetType(StrEnum):
    """Which objective is under pressure."""

    HIGH = "HIGH"
    LOW = "LOW"
    NONE = "NONE"


class BreakCapabilityState(StrEnum):
    """Overall breakout capability intensity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class BreakCapabilityInputs:
    """Read-only inputs for one Break Capability evaluation."""

    objectives: ObjectiveSnapshot
    initiative: InitiativeSnapshot
    response: ResponseSnapshot
    continuation: ContinuationSnapshot
    timestamp: float


@dataclass(frozen=True, slots=True)
class ObjectivePressureResult:
    """BK01 output."""

    pressure_score: float  # 0-100
    target_side: TargetSide
    target_type: TargetType
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResistanceEvaluationResult:
    """BK02 output. Higher = more resistance remaining."""

    resistance_score: float  # 0-100
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceAggregatorResult:
    """BK03 output — unified breakout assessment."""

    break_probability: float  # 0-100
    reasons: tuple[str, ...]
