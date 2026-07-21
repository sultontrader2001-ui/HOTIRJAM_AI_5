"""Objective Engine V2 — nearest eligible structural battlefield objectives.

Independent architecture module. Not wired to Decision or trading logic.
"""

from hotirjam_ai5.objective.objective_engine import ObjectiveEngine, evaluate_objectives
from hotirjam_ai5.objective.objective_models import ConfirmedSwing, ObjectiveInputs
from hotirjam_ai5.objective.objective_snapshot import ObjectiveSnapshot

__all__ = [
    "ConfirmedSwing",
    "ObjectiveEngine",
    "ObjectiveInputs",
    "ObjectiveSnapshot",
    "evaluate_objectives",
]
