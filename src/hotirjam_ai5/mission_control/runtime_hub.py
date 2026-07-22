"""Process-local runtime publication hub (H-7.2A).

The HOTIRJAM AI runner publishes already-existing observation objects here.
Mission Control only reads references — never creates runtime, never
calls snapshot / evaluate / on_tick.

One process → one hub → one runtime. No duplicated engines.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from hotirjam_ai5.dashboard.models import DashboardState
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle

if TYPE_CHECKING:
    from hotirjam_ai5.live_validator.loop_timing import LoopTimingSnapshot
    from hotirjam_ai5.live_validator.models import ValidatorFrame

_LOCK = threading.RLock()


@dataclass(slots=True)
class _HubSlots:
    """Holds references to objects owned by the runner."""

    dashboard: DashboardState | None = None
    frame: Any = None
    loop_timing: Any = None
    transition_summaries: tuple[str, ...] = ()
    publisher: str = "none"
    publish_count: int = 0


_SLOTS = _HubSlots()


class RuntimeHub:
    """Passive observation surface for Mission Control."""

    def publish_dashboard(self, state: DashboardState, *, publisher: str = "DashboardApp") -> None:
        """Store reference to an existing DashboardState (runner-owned)."""
        with _LOCK:
            _SLOTS.dashboard = state
            _SLOTS.publisher = publisher
            _SLOTS.publish_count += 1

    def publish_frame(
        self,
        frame: Any,
        *,
        publisher: str = "LiveValidatorApp",
        transition_summaries: tuple[str, ...] = (),
        loop_timing: Any = None,
    ) -> None:
        """Store reference to an existing ValidatorFrame (runner-owned)."""
        with _LOCK:
            _SLOTS.frame = frame
            if transition_summaries:
                _SLOTS.transition_summaries = transition_summaries
            if loop_timing is not None:
                _SLOTS.loop_timing = loop_timing
            _SLOTS.publisher = publisher
            _SLOTS.publish_count += 1

    def publish_loop_timing(self, timing: Any) -> None:
        with _LOCK:
            _SLOTS.loop_timing = timing
            _SLOTS.publish_count += 1

    def clear(self) -> None:
        """Test helper — does not create runtime objects."""
        with _LOCK:
            _SLOTS.dashboard = None
            _SLOTS.frame = None
            _SLOTS.loop_timing = None
            _SLOTS.transition_summaries = ()
            _SLOTS.publisher = "none"
            _SLOTS.publish_count = 0

    @property
    def publisher(self) -> str:
        with _LOCK:
            return _SLOTS.publisher

    @property
    def publish_count(self) -> int:
        with _LOCK:
            return _SLOTS.publish_count

    @property
    def dashboard(self) -> DashboardState | None:
        with _LOCK:
            return _SLOTS.dashboard

    @property
    def frame(self) -> Any:
        with _LOCK:
            return _SLOTS.frame

    def is_attached(self) -> bool:
        with _LOCK:
            return _SLOTS.dashboard is not None or _SLOTS.frame is not None

    def read_bundle(self, *, now: float | None = None) -> RuntimeBundle:
        """Build a presentation bundle from published references only."""
        with _LOCK:
            return RuntimeBundle(
                now=float(time.time() if now is None else now),
                dashboard=_SLOTS.dashboard,
                frame=_SLOTS.frame,
                loop_timing=_SLOTS.loop_timing,
                transition_summaries=_SLOTS.transition_summaries,
            )


_HUB = RuntimeHub()


def get_runtime_hub() -> RuntimeHub:
    """Process-wide hub singleton."""
    return _HUB


def reset_runtime_hub_for_tests() -> None:
    get_runtime_hub().clear()
