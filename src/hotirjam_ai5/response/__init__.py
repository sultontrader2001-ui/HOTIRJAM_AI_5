"""Response Engine (Module 03) — quality of opposing-side counter-response.

Independent architecture module. Not wired to Decision or trading logic.
"""

from hotirjam_ai5.response.counter_move_detector import detect_counter_move
from hotirjam_ai5.response.initiative_preservation import evaluate_initiative_preservation
from hotirjam_ai5.response.response_engine import ResponseEngine, evaluate_response
from hotirjam_ai5.response.response_models import (
    CounterMoveResult,
    InitiativePreservationResult,
    ResponseInputs,
    ResponseSide,
    ResponseState,
    ResponseStrengthResult,
)
from hotirjam_ai5.response.response_scorer import score_response
from hotirjam_ai5.response.response_snapshot import ResponseSnapshot
from hotirjam_ai5.response.response_strength import analyze_response_strength

__all__ = [
    "CounterMoveResult",
    "InitiativePreservationResult",
    "ResponseEngine",
    "ResponseInputs",
    "ResponseSide",
    "ResponseSnapshot",
    "ResponseState",
    "ResponseStrengthResult",
    "analyze_response_strength",
    "detect_counter_move",
    "evaluate_initiative_preservation",
    "evaluate_response",
    "score_response",
]
