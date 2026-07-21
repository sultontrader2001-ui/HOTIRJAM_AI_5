"""Candidate eligibility report — shared structural selection evidence.

Objective Engine V2 applies these labels; Developer View explains them.
"""

from __future__ import annotations

from hotirjam_ai5.objective_diagnostics.models import (
    CandidateCategory,
    LifecycleState,
    SwingDiagnostic,
    SwingSide,
)


def evaluate_eligibility(
    *,
    side: SwingSide,
    price: float,
    current_price: float,
    lifecycle: LifecycleState,
    category: CandidateCategory,
    depth: int,
    prominence: float,
    parent_swing_id: int | None,
) -> tuple[bool, tuple[str, ...]]:
    """Return (eligible, rejection_reasons) for diagnostic reporting."""
    reasons: list[str] = []

    if side is SwingSide.HIGH and not (price > current_price):
        reasons.append("Wrong side of price (HIGH not above current price)")
    if side is SwingSide.LOW and not (price < current_price):
        reasons.append("Wrong side of price (LOW not below current price)")

    if lifecycle is LifecycleState.BREACHED:
        reasons.append("Lifecycle BREACHED")
    if lifecycle is LifecycleState.SUPERSEDED:
        reasons.append("Lifecycle SUPERSEDED")
    if lifecycle is LifecycleState.ARCHIVED:
        reasons.append("Lifecycle ARCHIVED")

    if category is CandidateCategory.MICRO:
        reasons.append("Insufficient prominence" if prominence < 4.0 else "Category MICRO")
    if category is CandidateCategory.MINOR:
        reasons.append("Category MINOR (not MAJOR)")
    if depth >= 1 or parent_swing_id is not None:
        if category is not CandidateCategory.MAJOR:
            reasons.append("Nested inside parent")

    # Diagnostic eligibility: MAJOR + ACTIVE + correct side only.
    eligible = (
        category is CandidateCategory.MAJOR
        and lifecycle is LifecycleState.ACTIVE
        and (
            (side is SwingSide.HIGH and price > current_price)
            or (side is SwingSide.LOW and price < current_price)
        )
    )
    if eligible:
        return True, ()
    # Ensure at least one reason when not eligible.
    if not reasons:
        reasons.append("Not MAJOR+ACTIVE on correct side of price")
    # Deduplicate while preserving order.
    unique: list[str] = []
    for r in reasons:
        if r not in unique:
            unique.append(r)
    return False, tuple(unique)


def sort_candidates(diagnostics: list[SwingDiagnostic]) -> list[SwingDiagnostic]:
    """Order for ranked diagnostic report (not engine selection)."""
    category_rank = {
        CandidateCategory.MAJOR: 0,
        CandidateCategory.MINOR: 1,
        CandidateCategory.MICRO: 2,
    }
    lifecycle_rank = {
        LifecycleState.ACTIVE: 0,
        LifecycleState.SUPERSEDED: 1,
        LifecycleState.BREACHED: 2,
        LifecycleState.ARCHIVED: 3,
    }
    return sorted(
        diagnostics,
        key=lambda d: (
            category_rank[d.category],
            lifecycle_rank[d.lifecycle],
            0 if d.eligible else 1,
            d.distance_ticks,
            d.swing_id,
        ),
    )
