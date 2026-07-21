"""Objective structural classification and read-only evidence layer.

Objective Engine V2 consumes the same classification report used by Developer
View. This package remains deterministic and does not mutate engine state.
"""

from hotirjam_ai5.objective_diagnostics.candidate_report import (
    evaluate_eligibility,
    sort_candidates,
)
from hotirjam_ai5.objective_diagnostics.hierarchy_builder import (
    HierarchyNode,
    build_hierarchy,
)
from hotirjam_ai5.objective_diagnostics.models import (
    CandidateCategory,
    LifecycleState,
    ObjectiveAuditReport,
    ObjectiveDiagnosticsInputs,
    SwingDiagnostic,
    SwingSide,
)
from hotirjam_ai5.objective_diagnostics.objective_audit import (
    audit_objectives,
    format_audit_report,
)
from hotirjam_ai5.objective_diagnostics.significance_diagnostics import (
    classify_category,
    compute_persistence,
    compute_prominence_ticks,
    resolve_lifecycle,
)

__all__ = [
    "CandidateCategory",
    "HierarchyNode",
    "LifecycleState",
    "ObjectiveAuditReport",
    "ObjectiveDiagnosticsInputs",
    "SwingDiagnostic",
    "SwingSide",
    "audit_objectives",
    "build_hierarchy",
    "classify_category",
    "compute_persistence",
    "compute_prominence_ticks",
    "evaluate_eligibility",
    "format_audit_report",
    "resolve_lifecycle",
    "sort_candidates",
]
