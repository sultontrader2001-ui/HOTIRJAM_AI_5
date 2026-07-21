"""Decision evaluation models (Sprint 13).

Evaluation lifecycle only — never emits trading decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecisionEvaluationStatus(StrEnum):
    """Current state of the evaluation workflow."""

    IDLE = "IDLE"
    WAITING = "WAITING"
    EVALUATING = "EVALUATING"


@dataclass(frozen=True, slots=True)
class DecisionEvaluationSnapshot:
    """Whether evaluation can begin, derived from Decision Intent only."""

    timestamp: float
    status: DecisionEvaluationStatus
    evaluation_allowed: bool
    reason: str
    next_stage: str
