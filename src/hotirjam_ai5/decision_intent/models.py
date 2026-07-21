"""Decision intent models (Sprint 12).

Workflow controller only — never emits trading decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecisionIntent(StrEnum):
    """What the system should do next."""

    WAIT = "WAIT"
    OBSERVE = "OBSERVE"
    EVALUATE = "EVALUATE"


@dataclass(frozen=True, slots=True)
class DecisionIntentSnapshot:
    """Workflow intent derived from Decision Foundation only."""

    timestamp: float
    intent: DecisionIntent
    reason: str
    next_step: str
