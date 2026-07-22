"""Mission Control interactive app — presentation loop only (H-7.2)."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from typing import Any, TextIO

from hotirjam_ai5.dashboard.models import DashboardState
from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.mission_control.models import MissionWindow
from hotirjam_ai5.mission_control.runtime_bundle import (
    RuntimeBundle,
    read_lv_controller_latest,
    read_lv_journal_summaries,
)
from hotirjam_ai5.mission_control.runtime_hub import get_runtime_hub
from hotirjam_ai5.mission_control.shell import MissionControlShell


class _NullKeyboard:
    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        return None


class MissionControlApp:
    """Terminal shell host. Presentation only.

    May hold a Live Validator controller reference solely to read ``.latest``
    and ``.structural_transition_journal``. Never calls on_tick / evaluate_now.
    May hold an already-built ``DashboardState`` — never calls
    ``DashboardController.snapshot()`` (that path evaluates engines).
    """

    def __init__(
        self,
        *,
        shell: MissionControlShell | None = None,
        keyboard: object | None = None,
        display: TerminalDisplay | None = None,
        refresh_seconds: float = 0.25,
        sleep_fn: Callable[[float], None] | None = None,
        stdout: TextIO | None = None,
        lv_controller: Any | None = None,
        dashboard_state: DashboardState | None = None,
        loop_timing_reader: Callable[[], Any] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._shell = shell or MissionControlShell()
        self._keyboard = keyboard if keyboard is not None else _NullKeyboard()
        self._display = display or TerminalDisplay(stream=stdout or sys.stdout)
        self._refresh_seconds = max(0.05, float(refresh_seconds))
        self._sleep = sleep_fn or time.sleep
        self._running = False
        self._lv = lv_controller
        self._dashboard_state = dashboard_state
        self._loop_timing_reader = loop_timing_reader
        self._clock = clock or time.time

    @property
    def shell(self) -> MissionControlShell:
        return self._shell

    def _refresh_bundle(self) -> None:
        """Re-read published / attached objects only. No evaluate / on_tick / snapshot()."""
        hub = get_runtime_hub()
        if hub.is_attached():
            self._shell.set_bundle(hub.read_bundle(now=float(self._clock())))
            return
        frame = None
        summaries: tuple[str, ...] = ()
        if self._lv is not None:
            frame = read_lv_controller_latest(self._lv)
            summaries = read_lv_journal_summaries(self._lv)
        timing = None
        if self._loop_timing_reader is not None:
            timing = self._loop_timing_reader()
        self._shell.set_bundle(
            RuntimeBundle(
                now=float(self._clock()),
                dashboard=self._dashboard_state,
                frame=frame,
                loop_timing=timing,
                transition_summaries=summaries,
            )
        )

    def render_once(self) -> str:
        self._refresh_bundle()
        return self._shell.render()

    def run(self, *, max_frames: int | None = None) -> None:
        self._running = True
        enable = getattr(self._keyboard, "enable", None)
        if callable(enable):
            enable()
        self._display.prepare()
        frames = 0
        try:
            while self._running:
                key = getattr(self._keyboard, "poll_key", lambda: None)()
                if isinstance(key, str) and key:
                    if not self._shell.handle_key(key):
                        break
                text = self.render_once()
                self._display.render_frame(text)
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
                self._sleep(self._refresh_seconds)
        finally:
            disable = getattr(self._keyboard, "disable", None)
            if callable(disable):
                disable()
            self._display.shutdown()
            self._running = False


def _build_keyboard() -> object:
    try:
        from hotirjam_ai5.live_validator.keyboard_input import KeyboardInput

        return KeyboardInput()
    except Exception:
        return _NullKeyboard()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hotirjam-ai5-mission-control",
        description=(
            "HOTIRJAM AI 5 Mission Control — frozen / optional observer only. "
            "For Objective Engine live validation use: hotirjam-ai5-live-validator "
            "(classic Live Certification Dashboard, no --mission-control)."
        ),
    )
    parser.add_argument(
        "--window",
        choices=("cockpit", "laboratory", "developer"),
        default="cockpit",
        help="Initial window",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Render one frame to stdout and exit (no interactive loop)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional interactive frame cap (tests)",
    )
    parser.add_argument(
        "--from-hub",
        action="store_true",
        help="Read RuntimeHub only (must be published by an active runner in-process)",
    )
    args = parser.parse_args(argv)

    window = {
        "cockpit": MissionWindow.COCKPIT,
        "laboratory": MissionWindow.LABORATORY,
        "developer": MissionWindow.DEVELOPER,
    }[args.window]
    shell = MissionControlShell(window=window)
    if args.from_hub or get_runtime_hub().is_attached():
        shell.set_bundle(get_runtime_hub().read_bundle())

    if args.once:
        sys.stdout.write(shell.render())
        sys.stdout.write("\n")
        if not get_runtime_hub().is_attached():
            sys.stdout.write(
                "# NOTE: RuntimeHub empty — launch via "
                "`hotirjam-ai5 --mission-control` for live wiring.\n"
            )
        return 0

    app = MissionControlApp(shell=shell, keyboard=_build_keyboard())
    app.run(max_frames=args.max_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
