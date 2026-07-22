"""Observation session — record completed cycles; certify at end (H-8.0).

Uses existing Live Validator controller for live ticks (unchanged).
May read RuntimeHub without publishing or mutating it.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

from hotirjam_ai5.observation.models import ObservationCycle
from hotirjam_ai5.observation.recorder import record_from_frame
from hotirjam_ai5.observation.report import CertificationReport, build_certification_report


class ObservationSession:
    """Observe market architecture outputs. Never trades. Never orders."""

    def __init__(
        self,
        *,
        min_cycles: int = 1,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._min_cycles = max(1, int(min_cycles))
        self._clock = clock or time.time
        self._cycles: list[ObservationCycle] = []
        self._started: float | None = None
        self._ended: float | None = None
        self._orders_attempted = 0
        self._hub_mutated = False
        self._last_frame_id: int | None = None

    @property
    def cycles(self) -> tuple[ObservationCycle, ...]:
        return tuple(self._cycles)

    @property
    def cycle_count(self) -> int:
        return len(self._cycles)

    def start(self) -> None:
        self._started = float(self._clock())
        self._ended = None

    def record_frame(self, frame: Any, *, dashboard: Any | None = None) -> ObservationCycle:
        """Record one completed observation cycle from a published/evaluated frame."""
        if self._started is None:
            self.start()
        cycle = record_from_frame(
            frame,
            cycle_id=len(self._cycles) + 1,
            dashboard=dashboard,
        )
        self._cycles.append(cycle)
        self._last_frame_id = id(frame)
        return cycle

    def observe_hub(
        self,
        *,
        max_cycles: int = 100,
        poll_seconds: float = 0.05,
        max_seconds: float = 30.0,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> CertificationReport:
        """Poll RuntimeHub for newly published frames (read-only)."""
        from hotirjam_ai5.mission_control.runtime_hub import get_runtime_hub

        sleep = sleep_fn or time.sleep
        hub = get_runtime_hub()
        self.start()
        deadline = float(self._clock()) + max(0.0, max_seconds)
        seen: set[int] = set()

        while len(self._cycles) < max_cycles and float(self._clock()) < deadline:
            frame = hub.frame
            dash = hub.dashboard
            if frame is not None:
                fid = id(frame)
                if fid not in seen:
                    seen.add(fid)
                    self.record_frame(frame, dashboard=dash)
            sleep(poll_seconds)

        return self.finish()

    def observe_live(
        self,
        ticks: Iterable[Any],
        *,
        max_cycles: int | None = None,
        dashboard: Any | None = None,
    ) -> CertificationReport:
        """Drive existing LiveValidatorController with ticks; record each evaluation.

        Does not modify RuntimeHub. Does not send orders.
        """
        from hotirjam_ai5.live_validator.controller import LiveValidatorController

        controller = LiveValidatorController(log_every_evaluation=False)
        self.start()
        limit = max_cycles if max_cycles is not None else self._min_cycles
        for tick in ticks:
            if len(self._cycles) >= limit:
                break
            frame = controller.on_tick(tick)
            self.record_frame(frame, dashboard=dashboard)
        return self.finish()

    def observe_live_file(
        self,
        *,
        tick_path: str | None = None,
        max_cycles: int = 50,
        max_seconds: float = 60.0,
        poll_seconds: float = 0.05,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> CertificationReport:
        """Poll live NDJSON tick file via existing ingress + controller."""
        from hotirjam_ai5.live_data.ingress import LiveTickIngress
        from hotirjam_ai5.live_validator.controller import LiveValidatorController

        sleep = sleep_fn or time.sleep
        ingress = LiveTickIngress(path=tick_path) if tick_path else LiveTickIngress()
        controller = LiveValidatorController(log_every_evaluation=False)
        self.start()
        deadline = float(self._clock()) + max(0.0, max_seconds)

        while len(self._cycles) < max_cycles and float(self._clock()) < deadline:
            for tick in ingress.poll():
                frame = controller.on_tick(tick)
                self.record_frame(frame)
                if len(self._cycles) >= max_cycles:
                    break
            sleep(poll_seconds)

        return self.finish()

    def finish(self) -> CertificationReport:
        """Close session and build certification report."""
        if self._started is None:
            self._started = float(self._clock())
        self._ended = float(self._clock())
        duration = max(0.0, self._ended - self._started)
        return build_certification_report(
            self._cycles,
            duration_seconds=duration,
            min_cycles=self._min_cycles,
            orders_attempted=self._orders_attempted,
            hub_mutated=self._hub_mutated,
        )
