"""Hierarchy builder — parent/child nesting among confirmed swings.

Read-only diagnostics. Does not filter Objective Engine candidates.
"""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.objective import ConfirmedSwing
from hotirjam_ai5.objective_diagnostics.models import SwingSide


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    """One swing placed in a diagnostic hierarchy."""

    swing_id: int
    side: SwingSide
    swing: ConfirmedSwing
    parent_swing_id: int | None
    depth: int


@dataclass(frozen=True, slots=True)
class _Tagged:
    swing_id: int
    side: SwingSide
    swing: ConfirmedSwing


def build_hierarchy(
    highs: tuple[ConfirmedSwing, ...],
    lows: tuple[ConfirmedSwing, ...],
) -> tuple[HierarchyNode, ...]:
    """Assign parent and depth for each confirmed swing.

    Rule (deterministic, diagnostic):
    - Sort by confirmed_at ascending (missing → -inf), then by swing_id.
    - A HIGH's parent is the nearest earlier HIGH with a strictly higher price
      that has not been closed by an intervening higher HIGH.
    - A LOW's parent is the nearest earlier LOW with a strictly lower price
      that has not been closed by an intervening lower LOW.
    - Depth is parent chain length.
    """
    tagged: list[_Tagged] = []
    sid = 1
    for swing in highs:
        tagged.append(_Tagged(sid, SwingSide.HIGH, swing))
        sid += 1
    for swing in lows:
        tagged.append(_Tagged(sid, SwingSide.LOW, swing))
        sid += 1

    tagged.sort(
        key=lambda t: (
            t.swing.confirmed_at if t.swing.confirmed_at is not None else float("-inf"),
            t.swing_id,
        )
    )

    # Active open parents per side (stack of enclosing extremes).
    high_stack: list[_Tagged] = []
    low_stack: list[_Tagged] = []
    parents: dict[int, int | None] = {}

    for item in tagged:
        if item.side is SwingSide.HIGH:
            while high_stack and high_stack[-1].swing.price <= item.swing.price:
                high_stack.pop()
            parent = high_stack[-1] if high_stack else None
            parents[item.swing_id] = parent.swing_id if parent else None
            high_stack.append(item)
        else:
            while low_stack and low_stack[-1].swing.price >= item.swing.price:
                low_stack.pop()
            parent = low_stack[-1] if low_stack else None
            parents[item.swing_id] = parent.swing_id if parent else None
            low_stack.append(item)

    def depth_of(swing_id: int) -> int:
        d = 0
        cur = parents.get(swing_id)
        seen: set[int] = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            d += 1
            cur = parents.get(cur)
        return d

    nodes = [
        HierarchyNode(
            swing_id=t.swing_id,
            side=t.side,
            swing=t.swing,
            parent_swing_id=parents[t.swing_id],
            depth=depth_of(t.swing_id),
        )
        for t in tagged
    ]
    return tuple(nodes)
