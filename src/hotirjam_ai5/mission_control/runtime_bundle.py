"""Read-only runtime bundle for Mission Control (H-7.2).

Holds already-existing observation objects only.
Never calls evaluate / calculate / snapshot-that-evaluates / derive.
Never allocates engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from hotirjam_ai5.dashboard.models import DashboardState

if TYPE_CHECKING:
    from hotirjam_ai5.live_validator.loop_timing import LoopTimingSnapshot
    from hotirjam_ai5.live_validator.models import ValidatorFrame


@dataclass(frozen=True, slots=True)
class RuntimeBundle:
    """Existing runtime objects available for presentation binding.

    ``now`` is wall-clock for display_age only (not an engine input).
    """

    now: float
    dashboard: DashboardState | None = None
    frame: ValidatorFrame | None = None
    loop_timing: LoopTimingSnapshot | None = None
    # Pre-fetched journal tuples (already materialized). Optional.
    transition_summaries: tuple[str, ...] = ()


def bundle_from_live_validator(
    *,
    now: float,
    latest_frame: ValidatorFrame | None,
    loop_timing: LoopTimingSnapshot | None = None,
    transition_summaries: tuple[str, ...] = (),
    dashboard: DashboardState | None = None,
) -> RuntimeBundle:
    """Assemble a bundle from already-held LV objects (no controller calls)."""
    return RuntimeBundle(
        now=now,
        dashboard=dashboard,
        frame=latest_frame,
        loop_timing=loop_timing,
        transition_summaries=transition_summaries,
    )


def read_lv_controller_latest(controller: Any) -> Any:
    """Read ``controller.latest`` only. Never calls on_tick / evaluate_now."""
    return getattr(controller, "latest", None)


def read_lv_journal_summaries(controller: Any, *, limit: int = 8) -> tuple[str, ...]:
    """Read existing journal property; format strings only. No evaluate."""
    journal = getattr(controller, "structural_transition_journal", None)
    if not journal:
        return ()
    rows: list[str] = []
    for entry in tuple(journal)[-limit:]:
        seq = getattr(entry, "sequence", "?")
        cause = getattr(entry, "cause", "?")
        sid = getattr(entry, "swing_id", "?")
        rows.append(f"seq={seq} swing={sid} cause={cause}")
    return tuple(rows)
