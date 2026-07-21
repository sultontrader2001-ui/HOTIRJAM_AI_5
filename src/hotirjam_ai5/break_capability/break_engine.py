"""Break Capability Engine — sufficiency to break the active objective (Module 05).

Independent. Not wired to Decision, broker, or execution.
Does not modify Objective, Initiative, Response, or Continuation engines.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.break_capability.break_models import BreakCapabilityInputs
from hotirjam_ai5.break_capability.break_scorer import score_break_capability
from hotirjam_ai5.break_capability.break_snapshot import BreakCapabilitySnapshot
from hotirjam_ai5.break_capability.evidence_aggregator import aggregate_break_evidence
from hotirjam_ai5.break_capability.objective_pressure import measure_objective_pressure
from hotirjam_ai5.break_capability.resistance_evaluation import evaluate_resistance


def evaluate_break_capability(inputs: BreakCapabilityInputs) -> BreakCapabilitySnapshot:
    """Run BK01→BK04 and return a BreakCapabilitySnapshot.

    Pure function of upstream snapshots. Deterministic. No trade decisions.
    """
    pressure = measure_objective_pressure(
        objectives=inputs.objectives,
        initiative=inputs.initiative,
        response=inputs.response,
        continuation=inputs.continuation,
    )
    resistance = evaluate_resistance(
        objectives=inputs.objectives,
        pressure=pressure,
        response=inputs.response,
    )
    evidence = aggregate_break_evidence(
        pressure=pressure,
        resistance=resistance,
        initiative=inputs.initiative,
        response=inputs.response,
        continuation=inputs.continuation,
    )
    return score_break_capability(
        pressure=pressure,
        resistance=resistance,
        evidence=evidence,
        objectives=inputs.objectives,
        timestamp=inputs.timestamp,
    )


class BreakCapabilityEngine:
    """Stateful wrapper retaining the latest BreakCapabilitySnapshot."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest = BreakCapabilitySnapshot.empty(timestamp=self._clock())

    def evaluate(self, inputs: BreakCapabilityInputs) -> BreakCapabilitySnapshot:
        self._latest = evaluate_break_capability(inputs)
        return self._latest

    def snapshot(self) -> BreakCapabilitySnapshot:
        return self._latest
