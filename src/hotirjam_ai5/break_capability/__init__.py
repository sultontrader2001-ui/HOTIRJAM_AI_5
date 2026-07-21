"""Break Capability Engine (Module 05) — can the active objective be broken?

Independent architecture module. Not wired to Decision or trading logic.
"""

from hotirjam_ai5.break_capability.break_engine import (
    BreakCapabilityEngine,
    evaluate_break_capability,
)
from hotirjam_ai5.break_capability.break_models import (
    BreakCapabilityInputs,
    BreakCapabilityState,
    EvidenceAggregatorResult,
    ObjectivePressureResult,
    ResistanceEvaluationResult,
    TargetSide,
    TargetType,
)
from hotirjam_ai5.break_capability.break_scorer import score_break_capability
from hotirjam_ai5.break_capability.break_snapshot import BreakCapabilitySnapshot
from hotirjam_ai5.break_capability.evidence_aggregator import aggregate_break_evidence
from hotirjam_ai5.break_capability.objective_pressure import measure_objective_pressure
from hotirjam_ai5.break_capability.resistance_evaluation import evaluate_resistance

__all__ = [
    "BreakCapabilityEngine",
    "BreakCapabilityInputs",
    "BreakCapabilitySnapshot",
    "BreakCapabilityState",
    "EvidenceAggregatorResult",
    "ObjectivePressureResult",
    "ResistanceEvaluationResult",
    "TargetSide",
    "TargetType",
    "aggregate_break_evidence",
    "evaluate_break_capability",
    "evaluate_resistance",
    "measure_objective_pressure",
    "score_break_capability",
]
