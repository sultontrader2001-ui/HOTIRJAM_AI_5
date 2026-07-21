"""Live Validator application — real market stream, architecture observation only."""

from __future__ import annotations

import argparse
import select
import sys
import termios
import time
import tty
from collections.abc import Callable
from pathlib import Path

from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.live_data.ingress import LiveTickIngress
from hotirjam_ai5.live_data.paths import default_tick_path
from hotirjam_ai5.live_validator.controller import LiveValidatorController
from hotirjam_ai5.live_validator.display import render_validator_frame
from hotirjam_ai5.live_validator.logger import SnapshotLogger
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline

DEFAULT_POLL_SECONDS = 0.05
DEFAULT_REFRESH_SECONDS = 0.5
DEFAULT_BAR_SECONDS = 1.0
DEFAULT_TICK_SIZE = 0.25
DEFAULT_STALE_SECONDS = 3.0


class LiveValidatorApp:
    """Poll live ticks; run Objective→…→Break; display + log snapshots."""

    def __init__(
        self,
        *,
        controller: LiveValidatorController | None = None,
        ingress: LiveTickIngress | None = None,
        display: TerminalDisplay | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        refresh_seconds: float = DEFAULT_REFRESH_SECONDS,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        stale_seconds: float = DEFAULT_STALE_SECONDS,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        if refresh_seconds <= 0:
            raise ValueError("refresh_seconds must be positive")
        self._controller = controller or LiveValidatorController()
        self._ingress = ingress
        self._display = display or TerminalDisplay()
        self._poll_seconds = poll_seconds
        self._refresh_seconds = refresh_seconds
        self._sleep = sleep_fn
        self._clock = clock
        self._wall_clock = wall_clock
        self._stale_seconds = stale_seconds
        self._developer_mode = False
        self._last_tick_wall: float | None = None
        self._ticks_seen = 0

    @property
    def developer_mode(self) -> bool:
        return self._developer_mode

    def toggle_developer_mode(self) -> bool:
        """Flip Trader ↔ Developer view. Returns new mode."""
        self._developer_mode = not self._developer_mode
        return self._developer_mode

    def feed_status(self) -> str:
        """Presentation-only feed health from last accepted tick age."""
        if self._ticks_seen == 0 or self._last_tick_wall is None:
            return "WAITING"
        age = self._wall_clock() - self._last_tick_wall
        if age > self._stale_seconds:
            return "STALE"
        return "LIVE"

    def poll_once(self) -> int:
        """Pull new ticks into the controller. Returns accepted tick count."""
        if self._ingress is None:
            return 0
        ticks = self._ingress.poll()
        for tick in ticks:
            self._controller.on_tick(tick)
            self._last_tick_wall = self._wall_clock()
            self._ticks_seen += 1
        return len(ticks)

    def render_once(self) -> str:
        frame = self._controller.latest
        if frame.current_price is None:
            frame = self._controller.evaluate_now()
        text = render_validator_frame(
            frame,
            developer_mode=self._developer_mode,
            feed_status=self.feed_status(),
        )
        self._display.render_frame(text)
        return text

    def _poll_keyboard_toggle(self) -> None:
        """Non-blocking D / d toggle when stdin is a TTY."""
        if not sys.stdin.isatty():
            return
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
        except (OSError, ValueError):
            return
        if not ready:
            return
        try:
            ch = sys.stdin.read(1)
        except OSError:
            return
        if ch in {"d", "D"}:
            self.toggle_developer_mode()

    def run(self, *, max_frames: int | None = None) -> int:
        """Poll continuously; redraw on refresh cadence. Returns 0 on exit."""
        self._display.prepare()
        frames = 0
        last_render_at: float | None = None
        old_term: list | None = None
        if sys.stdin.isatty():
            try:
                old_term = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
            except (termios.error, OSError):
                old_term = None
        try:
            while max_frames is None or frames < max_frames:
                self.poll_once()
                self._poll_keyboard_toggle()
                now = self._clock()
                should_render = (
                    last_render_at is None
                    or (now - last_render_at) >= self._refresh_seconds
                )
                if should_render:
                    self.render_once()
                    last_render_at = now
                    frames += 1
                self._sleep(self._poll_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            if old_term is not None:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term)
                except (termios.error, OSError):
                    pass
            self._display.shutdown()
        return 0


def _default_log_path() -> Path:
    return Path.cwd() / "logs" / "live_validator_snapshots.ndjson"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HOTIRJAM AI 5 Live Validator — observation only. "
            "Runs Objective→Initiative→Response→Continuation→Break Capability. "
            "Decision and Execution are DISABLED. Press D to toggle Developer View."
        )
    )
    parser.add_argument(
        "--tick-file",
        type=Path,
        default=None,
        help="Path to mnq_ticks.ndjson (default: NinjaTrader UserDataDir)",
    )
    parser.add_argument("--symbol", default="MNQ", help="Expected symbol (default MNQ)")
    parser.add_argument(
        "--tick-size",
        type=float,
        default=DEFAULT_TICK_SIZE,
        help="Instrument tick size (default 0.25 for MNQ)",
    )
    parser.add_argument(
        "--bar-seconds",
        type=float,
        default=DEFAULT_BAR_SECONDS,
        help="OHLC bar duration in seconds (default 1.0)",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help="Ingress poll interval seconds",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=DEFAULT_REFRESH_SECONDS,
        help="Display refresh interval seconds",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="NDJSON snapshot log path (default: ./logs/live_validator_snapshots.ndjson)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Stop after N display frames (testing)",
    )
    parser.add_argument(
        "--developer",
        action="store_true",
        help="Start in Developer View (default is Trader View)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    tick_path = args.tick_file or default_tick_path()
    log_path = args.log_file or _default_log_path()

    logger = SnapshotLogger(log_path)
    from hotirjam_ai5.live_validator.candle_builder import TickBarBuilder
    from hotirjam_ai5.live_validator.swing_confirmer import SwingConfirmer

    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(tick_size=args.tick_size, symbol=args.symbol),
        bar_builder=TickBarBuilder(bar_seconds=args.bar_seconds),
        swing_confirmer=SwingConfirmer(),
        logger=logger,
    )
    ingress = LiveTickIngress(tick_path, expected_symbol=args.symbol)
    app = LiveValidatorApp(
        controller=controller,
        ingress=ingress,
        poll_seconds=args.poll,
        refresh_seconds=args.refresh,
    )
    if args.developer:
        app.toggle_developer_mode()
    return app.run(max_frames=args.max_frames)


if __name__ == "__main__":
    raise SystemExit(main())
