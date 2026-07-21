"""Continuation Engine (Module 04) — initiative continuing or fading.

Independent architecture module. Not wired to Decision or trading logic.
"""

from hotirjam_ai5.continuation.continuation_engine import (
    ContinuationEngine,
    evaluate_continuation,
)
from hotirjam_ai5.continuation.continuation_models import (
    ContinuationInputs,
    ContinuationSide,
    ContinuationState,
    ContinuationStrengthResult,
    MomentumDecayResult,
    PressurePersistenceResult,
)
from hotirjam_ai5.continuation.continuation_scorer import score_continuation
from hotirjam_ai5.continuation.continuation_snapshot import ContinuationSnapshot
from hotirjam_ai5.continuation.continuation_strength import measure_continuation_strength
from hotirjam_ai5.continuation.momentum_decay import measure_momentum_decay
from hotirjam_ai5.continuation.pressure_persistence import measure_pressure_persistence

__all__ = [
    "ContinuationEngine",
    "ContinuationInputs",
    "ContinuationSide",
    "ContinuationSnapshot",
    "ContinuationState",
    "ContinuationStrengthResult",
    "MomentumDecayResult",
    "PressurePersistenceResult",
    "evaluate_continuation",
    "measure_continuation_strength",
    "measure_momentum_decay",
    "measure_pressure_persistence",
    "score_continuation",
]
