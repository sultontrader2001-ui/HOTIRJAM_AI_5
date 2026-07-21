"""Decision assessment models (Sprint 14).

Final evaluation standardization only — never emits trading decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecisionAssessmentState(StrEnum):
    """Standardized assessment outcome before any future trade decision."""

    BLOCKED = "BLOCKED"
    REVIEW = "REVIEW"
    READY = "READY"


@dataclass(frozen=True, slots=True)
class DecisionAssessmentSnapshot:
    """Assessment result derived from Decision Evaluation only."""

    timestamp: float
    assessment_state: DecisionAssessmentState
    assessment_ready: bool
    reason: str
    next_stage: str
