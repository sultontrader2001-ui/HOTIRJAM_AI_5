"""Objective structural evidence models shared by selection and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hotirjam_ai5.objective.objective_models import ConfirmedSwing


class SwingSide(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"


class LifecycleState(StrEnum):
    ACTIVE = "ACTIVE"
    BREACHED = "BREACHED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class CandidateCategory(StrEnum):
    MICRO = "MICRO"
    MINOR = "MINOR"
    MAJOR = "MAJOR"


@dataclass(frozen=True, slots=True)
class SwingDiagnostic:
    """Full diagnostic record for one confirmed swing."""

    swing_id: int
    side: SwingSide
    price: float
    confirmed_at: float | None
    distance_ticks: float
    current_strength: float
    parent_swing_id: int | None
    hierarchy_depth: int
    persistence: float  # 0-100 diagnostic
    prominence: float  # ticks
    lifecycle: LifecycleState
    category: CandidateCategory
    eligible: bool
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObjectiveDiagnosticsInputs:
    """Inputs for a read-only structural audit."""

    current_price: float
    tick_size: float
    confirmed_highs: tuple[ConfirmedSwing, ...]
    confirmed_lows: tuple[ConfirmedSwing, ...]
    timestamp: float
    # Optional OHLC extremes after confirmation for richer breach detection.
    # When omitted, breach uses current_price only.
    session_high: float | None = None
    session_low: float | None = None


@dataclass(frozen=True, slots=True)
class ObjectiveAuditReport:
    """Ranked diagnostic landscape (not Objective Engine output)."""

    timestamp: float
    current_price: float
    tick_size: float
    highs: tuple[SwingDiagnostic, ...]
    lows: tuple[SwingDiagnostic, ...]
    summary_lines: tuple[str, ...]
    hierarchy_version: int = 0
    registry_size: int = 0
    transition_count: int = 0
    checkpoint_version: int = 0
