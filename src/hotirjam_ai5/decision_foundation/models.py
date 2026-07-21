"""Decision foundation models (Sprint 10).

Readiness gate only — never emits trading decisions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecisionFoundationSnapshot:
    """Whether the observation layer is complete enough for a future decision."""

    timestamp: float
    ready: bool
    blocking_reason: str
    required_data_complete: bool
    context_valid: bool
    observation_complete: bool
    summary: str
