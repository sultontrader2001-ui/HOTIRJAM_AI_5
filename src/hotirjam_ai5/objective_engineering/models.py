"""Engineering Validation models — read-only evidence records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ObjectiveSide(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"


class ReasonClass(StrEnum):
    """Inferred reason class (observation). Not an Objective Engine API."""

    FIRST_ASSIGNMENT = "FIRST_ASSIGNMENT"
    UNCHANGED = "UNCHANGED"
    NEARER_ELIGIBLE = "NEARER_ELIGIBLE"
    UNEXPECTED_NOT_NEARER = "UNEXPECTED_NOT_NEARER"
    CONFIRMED_BROKEN = "CONFIRMED_BROKEN"
    LIFECYCLE_SUPERSEDED = "LIFECYCLE_SUPERSEDED"
    CLEARED_UNEXPLAINED = "CLEARED_UNEXPLAINED"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class ObjectiveEngineeringSample:
    """One evaluate observation of Objective HIGH/LOW + persistence."""

    sample_id: int
    timestamp: float
    current_price: float | None
    high_price: float | None
    high_distance_ticks: float | None
    high_strength: float | None
    high_state: str | None
    high_reason: str
    low_price: float | None
    low_distance_ticks: float | None
    low_strength: float | None
    low_state: str | None
    low_reason: str
    high_changed: bool
    low_changed: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ObjectiveChangeEvent:
    """Edge: identity or persistence-state change on one side."""

    change_id: int
    sample_id: int
    timestamp: float
    side: str
    from_price: float | None
    to_price: float | None
    from_state: str | None
    to_state: str | None
    from_distance_ticks: float | None
    to_distance_ticks: float | None
    reason: str
    current_price: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ObjectiveAnomaly:
    """Immediate engineering finding (not Formal Validation FAIL)."""

    anomaly_id: int
    sample_id: int
    timestamp: float
    code: str
    side: str | None
    detail: str
    current_price: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def highlight_line(self) -> str:
        side = self.side or "-"
        return (
            f"[OBJECTIVE_EV_ANOMALY] id={self.anomaly_id} "
            f"sample={self.sample_id} code={self.code} side={side} "
            f"ts={self.timestamp:.3f} price={self.current_price} | {self.detail}"
        )
