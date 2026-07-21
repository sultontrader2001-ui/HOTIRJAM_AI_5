"""Market context aggregation models (Sprint 9).

Observation aggregator only — never emits trading advice.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatisticsSnapshot:
    """Immutable statistics values for context aggregation."""

    tick_count: int = 0
    tick_rate: float = 0.0
    running_time_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class MarketContextSnapshot:
    """Unified read-only market context from existing observation layers."""

    timestamp: float
    state: str
    state_reason: str
    transition: str
    transition_changed: bool
    transition_duration: float
    behavior: str
    behavior_reason: str
    feed_status: str
    feed_quality: str
    dom_status: str
    dom_quality: str
    tick_rate: float
    spread: float | None
    summary: str
