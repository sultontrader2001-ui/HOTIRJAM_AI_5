"""Mission Control interactive app — presentation loop only (H-7.1)."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from typing import TextIO

from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.mission_control.shell import MissionControlShell
from hotirjam_ai5.mission_control.models import MissionWindow


class _NullKeyboard:
    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        return None


class MissionControlApp:
    """Terminal shell host. No engines. No ingress. Presentation only."""

    def __init__(
        self,
        *,
        shell: MissionControlShell | None = None,
        keyboard: object | None = None,
        display: TerminalDisplay | None = None,
        refresh_seconds: float = 0.25,
        sleep_fn: Callable[[float], None] | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._shell = shell or MissionControlShell()
        self._keyboard = keyboard if keyboard is not None else _NullKeyboard()
        self._display = display or TerminalDisplay(stream=stdout or sys.stdout)
        self._refresh_seconds = max(0.05, float(refresh_seconds))
        self._sleep = sleep_fn or time.sleep
        self._running = False

    @property
    def shell(self) -> MissionControlShell:
        return self._shell

    def render_once(self) -> str:
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
    """Best-effort keyboard; falls back to null if unavailable."""
    try:
        from hotirjam_ai5.live_validator.keyboard_input import KeyboardInput

        return KeyboardInput()
    except Exception:
        return _NullKeyboard()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hotirjam-ai5-mission-control",
        description="HOTIRJAM AI 5 Mission Control shell (H-7.1) — read-only UI.",
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
    args = parser.parse_args(argv)

    window = {
        "cockpit": MissionWindow.COCKPIT,
        "laboratory": MissionWindow.LABORATORY,
        "developer": MissionWindow.DEVELOPER,
    }[args.window]
    shell = MissionControlShell(window=window)

    if args.once:
        sys.stdout.write(shell.render())
        sys.stdout.write("\n")
        return 0

    app = MissionControlApp(shell=shell, keyboard=_build_keyboard())
    app.run(max_frames=args.max_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
