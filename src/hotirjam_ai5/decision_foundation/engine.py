"""Decision Foundation Engine — observation completeness gate only."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.decision_foundation.models import DecisionFoundationSnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot

READY_SUMMARY = "Observation layer complete."
WAITING_CONTEXT = "Waiting for market context."
FEED_UNAVAILABLE = "Feed unavailable."
MISSING_OBSERVATION = "Missing observation data."


class DecisionFoundationEngine:
    """Evaluates whether MarketContext is complete enough for a future decision.

    Consumes only MarketContextSnapshot. Never produces trading advice.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = DecisionFoundationSnapshot(
            timestamp=self._clock(),
            ready=False,
            blocking_reason=WAITING_CONTEXT,
            required_data_complete=False,
            context_valid=False,
            observation_complete=False,
            summary=WAITING_CONTEXT,
        )

    def evaluate(
        self,
        context: MarketContextSnapshot | None,
    ) -> DecisionFoundationSnapshot:
        """Assess observation completeness from MarketContext only."""
        self._latest = evaluate_decision_foundation(context, timestamp=self._clock())
        return self._latest

    def snapshot(self) -> DecisionFoundationSnapshot:
        """Return the latest readiness assessment without re-evaluating."""
        return self._latest


def evaluate_decision_foundation(
    context: MarketContextSnapshot | None,
    *,
    timestamp: float,
) -> DecisionFoundationSnapshot:
    """Pure readiness check against MarketContextSnapshot fields only."""
    if context is None:
        return DecisionFoundationSnapshot(
            timestamp=timestamp,
            ready=False,
            blocking_reason=WAITING_CONTEXT,
            required_data_complete=False,
            context_valid=False,
            observation_complete=False,
            summary=WAITING_CONTEXT,
        )

    required_data_complete = _required_data_complete(context)
    context_valid = _context_valid(context)
    observation_complete = required_data_complete and context_valid

    if context.feed_status in ("DISCONNECTED", "STALE"):
        return DecisionFoundationSnapshot(
            timestamp=timestamp,
            ready=False,
            blocking_reason=FEED_UNAVAILABLE,
            required_data_complete=required_data_complete,
            context_valid=context_valid,
            observation_complete=False,
            summary=FEED_UNAVAILABLE,
        )

    if not required_data_complete:
        return DecisionFoundationSnapshot(
            timestamp=timestamp,
            ready=False,
            blocking_reason=MISSING_OBSERVATION,
            required_data_complete=False,
            context_valid=context_valid,
            observation_complete=False,
            summary=MISSING_OBSERVATION,
        )

    if not context_valid:
        reason = (
            WAITING_CONTEXT
            if context.state == "UNKNOWN" or context.summary.startswith("Insufficient")
            else MISSING_OBSERVATION
        )
        return DecisionFoundationSnapshot(
            timestamp=timestamp,
            ready=False,
            blocking_reason=reason,
            required_data_complete=required_data_complete,
            context_valid=False,
            observation_complete=False,
            summary=reason,
        )

    return DecisionFoundationSnapshot(
        timestamp=timestamp,
        ready=True,
        blocking_reason="",
        required_data_complete=True,
        context_valid=True,
        observation_complete=True,
        summary=READY_SUMMARY,
    )


def _required_data_complete(context: MarketContextSnapshot) -> bool:
    return bool(
        context.state
        and context.behavior
        and context.summary
        and context.feed_status
        and context.feed_quality
        and context.transition
    )


def _context_valid(context: MarketContextSnapshot) -> bool:
    if context.state == "UNKNOWN":
        return False
    if context.behavior == "UNKNOWN":
        return False
    if context.summary.startswith("Insufficient"):
        return False
    return True
