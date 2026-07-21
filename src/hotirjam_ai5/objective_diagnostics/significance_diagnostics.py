"""Significance / lifecycle classification for confirmed swings.

Objective Engine V2 and Developer View consume the same deterministic labels.
"""

from __future__ import annotations

from hotirjam_ai5.objective_diagnostics.hierarchy_builder import HierarchyNode
from hotirjam_ai5.objective_diagnostics.models import (
    CandidateCategory,
    LifecycleState,
    SwingSide,
)

# Existing audited structural cutoffs shared by selection and diagnostics.
_MICRO_PROMINENCE_TICKS = 4.0
_MAJOR_PROMINENCE_TICKS = 12.0
_MAJOR_PERSISTENCE_MIN = 55.0
_ZONE_TICKS = 2.0


def compute_prominence_ticks(
    node: HierarchyNode,
    nodes: tuple[HierarchyNode, ...],
    *,
    tick_size: float,
) -> float:
    """Smaller excursion to nearest opposite-side pivots (ticks)."""
    if tick_size <= 0.0:
        return 0.0
    opposite = SwingSide.LOW if node.side is SwingSide.HIGH else SwingSide.HIGH
    opposites = [n for n in nodes if n.side is opposite]
    if not opposites:
        # Fall back to strength-implied scale when no opposite exists.
        return max(0.0, node.swing.strength / 10.0)

    distances = [abs(node.swing.price - o.swing.price) / tick_size for o in opposites]
    distances.sort()
    if len(distances) == 1:
        return distances[0]
    # Use the nearer two opposing references when available.
    return min(distances[0], distances[1])


def compute_persistence(node: HierarchyNode, prominence_ticks: float) -> float:
    """0–100 diagnostic persistence from depth, strength, and prominence."""
    depth_penalty = min(40.0, node.depth * 15.0)
    prom_score = min(50.0, (prominence_ticks / _MAJOR_PROMINENCE_TICKS) * 50.0)
    strength_part = max(0.0, min(50.0, node.swing.strength * 0.5))
    raw = strength_part + prom_score - depth_penalty
    return max(0.0, min(100.0, raw))


def classify_category(
    *,
    depth: int,
    prominence_ticks: float,
    persistence: float,
) -> CandidateCategory:
    """Diagnostic category label from structural facts."""
    if depth >= 1 and prominence_ticks < _MAJOR_PROMINENCE_TICKS:
        if prominence_ticks < _MICRO_PROMINENCE_TICKS:
            return CandidateCategory.MICRO
        return CandidateCategory.MINOR
    if (
        depth == 0
        and prominence_ticks >= _MAJOR_PROMINENCE_TICKS
        and persistence >= _MAJOR_PERSISTENCE_MIN
    ):
        return CandidateCategory.MAJOR
    if prominence_ticks < _MICRO_PROMINENCE_TICKS:
        return CandidateCategory.MICRO
    if depth == 0 and prominence_ticks >= _MICRO_PROMINENCE_TICKS:
        return CandidateCategory.MINOR
    return CandidateCategory.MINOR


def resolve_lifecycle(
    node: HierarchyNode,
    nodes: tuple[HierarchyNode, ...],
    *,
    current_price: float,
    tick_size: float,
    session_high: float | None,
    session_low: float | None,
) -> LifecycleState:
    """Stateless fallback lifecycle; penetration is only a challenge."""
    extreme_high = session_high if session_high is not None else current_price
    extreme_low = session_low if session_low is not None else current_price

    if node.side is SwingSide.HIGH and extreme_high > node.swing.price:
        return LifecycleState.CHALLENGED
    if node.side is SwingSide.LOW and extreme_low < node.swing.price:
        return LifecycleState.CHALLENGED

    # Superseded: later same-side swing within zone ticks, not itself.
    if tick_size <= 0.0:
        return LifecycleState.ACTIVE
    zone = _ZONE_TICKS * tick_size
    for other in nodes:
        if other.swing_id == node.swing_id or other.side is not node.side:
            continue
        node_t = node.swing.confirmed_at
        other_t = other.swing.confirmed_at
        if node_t is None or other_t is None:
            continue
        if other_t <= node_t:
            continue
        if abs(other.swing.price - node.swing.price) <= zone:
            return LifecycleState.SUPERSEDED
    return LifecycleState.ACTIVE
