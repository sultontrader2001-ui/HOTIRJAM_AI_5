"""Terminal dashboard entry point with live NinjaTrader tick + DOM ingress."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from hotirjam_ai5.dashboard.controller import DEFAULT_STALE_SECONDS, DashboardController
from hotirjam_ai5.dashboard.feed_health import DEFAULT_STALL_SECONDS
from hotirjam_ai5.dashboard.renderer import DashboardRenderer
from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.live_data.dom_ingress import LiveDomIngress
from hotirjam_ai5.live_data.ingress import LiveTickIngress
from hotirjam_ai5.live_data.paths import default_dom_path, default_tick_path

# Display refresh is throttled; ingress polling stays faster.
MIN_REFRESH_SECONDS = 0.25
MAX_REFRESH_SECONDS = 0.5
DEFAULT_REFRESH_SECONDS = 0.25
DEFAULT_POLL_SECONDS = 0.05


def clamp_refresh_seconds(value: float) -> float:
    """Keep dashboard refresh within the 250–500 ms UI budget."""
    if value <= 0:
        raise ValueError("refresh_seconds must be positive")
    return min(MAX_REFRESH_SECONDS, max(MIN_REFRESH_SECONDS, value))


class DashboardApp:
    """Polls live ticks/DOM in real time; redraws the terminal on a slower cadence."""

    def __init__(
        self,
        *,
        controller: DashboardController | None = None,
        ingress: LiveTickIngress | None = None,
        dom_ingress: LiveDomIngress | None = None,
        renderer: DashboardRenderer | None = None,
        display: TerminalDisplay | None = None,
        refresh_seconds: float = DEFAULT_REFRESH_SECONDS,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._refresh_seconds = clamp_refresh_seconds(refresh_seconds)
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        self._controller = controller or DashboardController()
        self._ingress = ingress
        self._dom_ingress = dom_ingress
        self._renderer = renderer or DashboardRenderer()
        self._display = display or TerminalDisplay()
        self._poll_seconds = poll_seconds
        self._sleep = sleep_fn
        self._clock = clock

    @property
    def refresh_seconds(self) -> float:
        return self._refresh_seconds

    @property
    def poll_seconds(self) -> float:
        return self._poll_seconds

    def poll_ingress(self) -> int:
        """Pull new live ticks into the controller. Returns accepted tick count."""
        if self._ingress is None:
            return 0
        ticks = self._ingress.poll()
        for tick in ticks:
            self._controller.on_tick(tick)
        return len(ticks)

    def poll_dom_ingress(self) -> int:
        """Pull new live DOM snapshots into the controller."""
        if self._dom_ingress is None:
            return 0
        snapshots = self._dom_ingress.poll()
        for snapshot in snapshots:
            self._controller.on_dom(snapshot)
        return len(snapshots)

    def poll_once(self) -> None:
        """Real-time ingest + health evaluation (no terminal draw)."""
        self.poll_ingress()
        self.poll_dom_ingress()
        self._controller.check_connection_health()

    def render_once(self) -> str:
        """Render the current snapshot to the terminal (diff update)."""
        state = self._controller.snapshot()
        text = self._renderer.render(state)
        self._display.render_frame(text)
        return text

    def run(self, *, max_frames: int | None = None) -> int:
        """Poll continuously; redraw at most every ``refresh_seconds``.

        ``max_frames`` limits display frames (not poll cycles).
        Returns 0 on clean exit.
        """
        self._display.prepare()
        self._controller.start()
        frames = 0
        last_render_at = None
        try:
            while max_frames is None or frames < max_frames:
                self.poll_once()
                now = self._clock()
                should_render = (
                    last_render_at is None
                    or (now - last_render_at) >= self._refresh_seconds
                )
                if should_render:
                    self.render_once()
                    last_render_at = now
                    frames += 1
                    if max_frames is not None and frames >= max_frames:
                        break
                self._sleep(self._poll_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            self._display.shutdown()
            self._controller.stop()
        return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HOTIRJAM AI 5 — live terminal dashboard (NinjaTrader ticks + DOM)",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=DEFAULT_REFRESH_SECONDS,
        help=(
            f"Dashboard redraw interval in seconds "
            f"(clamped to {MIN_REFRESH_SECONDS}-{MAX_REFRESH_SECONDS}, "
            f"default: {DEFAULT_REFRESH_SECONDS})"
        ),
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help=f"Tick/DOM poll interval in seconds (default: {DEFAULT_POLL_SECONDS})",
    )
    parser.add_argument(
        "--symbol",
        default="MNQ",
        help="Expected symbol (default: MNQ)",
    )
    parser.add_argument(
        "--tick-file",
        type=Path,
        default=None,
        help="NT01 NDJSON path (default: NinjaTrader UserDataDir/HOTIRJAM/mnq_ticks.ndjson)",
    )
    parser.add_argument(
        "--dom-file",
        type=Path,
        default=None,
        help="NT04 NDJSON path (default: NinjaTrader UserDataDir/HOTIRJAM/mnq_dom.ndjson)",
    )
    parser.add_argument(
        "--stall-seconds",
        type=float,
        default=DEFAULT_STALL_SECONDS,
        help=f"Seconds without updates before stalled (default: {DEFAULT_STALL_SECONDS})",
    )
    parser.add_argument(
        "--stale-seconds",
        type=float,
        default=DEFAULT_STALE_SECONDS,
        help=f"Seconds without updates before connection lost (default: {DEFAULT_STALE_SECONDS})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry used by ``python -m hotirjam_ai5`` and the console script."""
    args = build_arg_parser().parse_args(argv)
    tick_path = args.tick_file or default_tick_path()
    dom_path = args.dom_file or default_dom_path()
    controller = DashboardController(
        symbol=args.symbol,
        stall_seconds=args.stall_seconds,
        stale_seconds=args.stale_seconds,
    )
    app = DashboardApp(
        controller=controller,
        ingress=LiveTickIngress(tick_path, expected_symbol=args.symbol),
        dom_ingress=LiveDomIngress(dom_path, expected_symbol=args.symbol),
        refresh_seconds=args.refresh,
        poll_seconds=args.poll,
    )
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
