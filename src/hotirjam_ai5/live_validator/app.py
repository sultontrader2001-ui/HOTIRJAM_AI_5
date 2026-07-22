"""Live Validator application — real market stream, architecture observation only."""

from __future__ import annotations

import argparse
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.live_data.ingress import LiveTickIngress
from hotirjam_ai5.live_data.ingress_poll_snapshot import IngressPollSnapshot
from hotirjam_ai5.live_data.paths import default_dom_path, default_tick_path
from hotirjam_ai5.live_validator.certification_dashboard import (
    AuditLog,
    MarketTelemetry,
)
from hotirjam_ai5.retention import (
    get_retention_stats,
    load_retention_config,
)
from hotirjam_ai5.live_validator.controller import LiveValidatorController
from hotirjam_ai5.live_validator.display import render_validator_frame
from hotirjam_ai5.live_validator.idc import idc_page_for_key, render_idc
from hotirjam_ai5.live_validator.keyboard_input import KeyboardInput
from hotirjam_ai5.live_validator.logger import SnapshotLogger
from hotirjam_ai5.live_validator.loop_timing import (
    LoopTimingSnapshot,
    add_keyboard_ms,
    add_poll_ms,
    add_render_ms,
    add_sleep_ms,
    begin_loop_sample,
    finish_loop_sample,
    latest_loop_timing,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.live_validator.presentation_mode import IdcPage, PresentationMode

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
        keyboard: KeyboardInput | None = None,
        mission_control: bool = False,
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
        self._presentation_mode = PresentationMode.DASHBOARD
        self._idc_page = IdcPage.MENU
        self._developer_mode = False
        self._last_tick_wall: float | None = None
        self._ticks_seen = 0
        self._keyboard = keyboard or KeyboardInput()
        # Presentation-only feed telemetry for the certification dashboard.
        # Never feeds any engine.
        self._last_bid: float | None = None
        self._last_ask: float | None = None
        self._last_spread: float | None = None
        self._last_latency_ms: float | None = None
        self._tick_wall_times: deque[float] = deque()
        self._audit = AuditLog()
        self._started_wall: float | None = None
        self._last_feed_status: str | None = None
        self._tick_path: Path | None = None
        self._dom_path: Path | None = None
        self._snapshot_log_path: Path | None = None
        self._retention_checks = 0
        self._mission_control = bool(mission_control)
        self._mc_shell = None
        if self._mission_control:
            from hotirjam_ai5.mission_control.shell import MissionControlShell

            self._mc_shell = MissionControlShell()

    @property
    def presentation_mode(self) -> PresentationMode:
        return self._presentation_mode

    @property
    def idc_page(self) -> IdcPage:
        return self._idc_page

    @property
    def developer_mode(self) -> bool:
        return self._developer_mode

    def enter_idc(self) -> bool:
        """Open IDC Main Menu. Rendering only — does not touch the runtime."""
        if (
            self._presentation_mode is PresentationMode.IDC
            and self._idc_page is IdcPage.MENU
        ):
            return False
        self._presentation_mode = PresentationMode.IDC
        self._idc_page = IdcPage.MENU
        return True

    def exit_idc(self) -> bool:
        """Leave IDC and return to the Certification Dashboard."""
        if self._presentation_mode is not PresentationMode.IDC:
            return False
        self._presentation_mode = PresentationMode.DASHBOARD
        self._idc_page = IdcPage.MENU
        self._developer_mode = False
        return True

    def toggle_developer_mode(self) -> bool:
        """Flip Trader ↔ Developer view. No-op while IDC is open."""
        if self._presentation_mode is PresentationMode.IDC:
            return self._developer_mode
        self._developer_mode = not self._developer_mode
        return self._developer_mode

    def exit_developer_mode(self) -> bool:
        """Return to the Certification Dashboard. Returns True if view changed."""
        if not self._developer_mode:
            return False
        self._developer_mode = False
        return True

    def configure_retention_paths(
        self,
        *,
        tick_path: Path | None = None,
        dom_path: Path | None = None,
        snapshot_log_path: Path | None = None,
    ) -> None:
        """Bind market/log paths for H-6.7 retention enforcement and diagnostics."""
        self._tick_path = None if tick_path is None else Path(tick_path)
        self._dom_path = None if dom_path is None else Path(dom_path)
        self._snapshot_log_path = (
            None if snapshot_log_path is None else Path(snapshot_log_path)
        )

    def feed_status(self) -> str:
        """Presentation-only feed health from last accepted tick age."""
        if self._ticks_seen == 0 or self._last_tick_wall is None:
            return "WAITING"
        age = self._wall_clock() - self._last_tick_wall
        if age > self._stale_seconds:
            return "STALE"
        return "LIVE"

    def uptime_seconds(self) -> float | None:
        """Seconds since ``run()`` started, or None before start."""
        if self._started_wall is None:
            return None
        return max(0.0, self._wall_clock() - self._started_wall)

    @property
    def audit_log(self) -> AuditLog:
        return self._audit

    @property
    def loop_timing(self) -> LoopTimingSnapshot | None:
        """Read-only latest main-loop timing sample (H-6.6.4). Never displayed here."""
        try:
            return latest_loop_timing()
        except Exception:
            return None

    @property
    def ingress_poll(self) -> IngressPollSnapshot | None:
        """TEMPORARY — last LiveTickIngress.poll() snapshot (Feed WAITING triage)."""
        if self._ingress is None:
            return None
        return getattr(self._ingress, "last_poll", None)

    def retention_snapshot(self):
        """H-6.7 retention diagnostics for the Performance page."""
        try:
            from hotirjam_ai5.retention import RetentionSnapshot

            stats = get_retention_stats()
            stats.config = load_retention_config()
            stats.snapshot_log_path = self._snapshot_log_path
            stats.tick_path = self._tick_path
            stats.dom_path = self._dom_path
            try:
                hierarchy = self._controller._pipeline.structural_hierarchy
                stats.journal_entries = len(hierarchy.journal)
                stats.hierarchy_version = hierarchy.hierarchy_version
            except Exception:
                pass
            snap = stats.snapshot()
            assert isinstance(snap, RetentionSnapshot)
            return snap
        except Exception:
            return None

    def _enforce_market_file_retention(self) -> None:
        """Storage maintenance AFTER poll — never touches unconsumed market bytes."""
        self._retention_checks += 1
        # At most every ~1s at default 50ms poll.
        if self._retention_checks % 20 != 0:
            return
        try:
            cfg = load_retention_config()
            if self._ingress is not None:
                apply = getattr(self._ingress, "apply_safe_storage_retention", None)
                if callable(apply):
                    apply(max_bytes=cfg.tick_ndjson_max_bytes)
            # DOM: only when a LiveDomIngress is bound (dashboard); path-only is unsafe.
        except Exception:
            return

    def poll_once(self) -> int:
        """Pull new ticks into the controller. Returns accepted tick count."""
        if self._ingress is None:
            return 0
        ticks = self._ingress.poll()
        for tick in ticks:
            self._controller.on_tick(tick)
            wall = self._wall_clock()
            self._last_tick_wall = wall
            self._ticks_seen += 1
            # Display-only feed telemetry (dashboard MARKET section).
            self._last_bid = tick.bid
            self._last_ask = tick.ask
            self._last_spread = tick.spread
            self._last_latency_ms = max(0.0, (wall - tick.timestamp) * 1000.0)
            self._tick_wall_times.append(wall)
        # Retention only after ticks were delivered to the controller.
        self._enforce_market_file_retention()
        return len(ticks)

    def _tick_rate(self) -> float | None:
        """Ticks accepted in the trailing 1s window. Presentation only."""
        if self._ticks_seen == 0:
            return None
        now = self._wall_clock()
        while self._tick_wall_times and now - self._tick_wall_times[0] > 1.0:
            self._tick_wall_times.popleft()
        return float(len(self._tick_wall_times))

    def _track_feed_transition(self, status: str) -> None:
        """Record feed status changes in the presentation-only audit log."""
        if status == self._last_feed_status:
            return
        level = "WARNING" if status == "STALE" else "INFO"
        self._audit.record(level, f"Feed {status}", timestamp=self._wall_clock())
        self._last_feed_status = status

    def _publish_runtime(self, frame: object) -> None:
        """Publish existing LV frame to the process hub (H-7.2A)."""
        from hotirjam_ai5.mission_control.runtime_bundle import read_lv_journal_summaries
        from hotirjam_ai5.mission_control.runtime_hub import get_runtime_hub

        timing = self.loop_timing
        get_runtime_hub().publish_frame(
            frame,
            publisher="LiveValidatorApp",
            transition_summaries=read_lv_journal_summaries(self._controller),
            loop_timing=timing,
        )

    def render_once(self) -> str:
        # IDC is presentation-only: never calls evaluate(); engine pages
        # observe the latest frame / journal already produced by the runtime.
        if self._presentation_mode is PresentationMode.IDC:
            status = self.feed_status()
            self._track_feed_transition(status)
            frame = self._controller.latest
            self._publish_runtime(frame)
            transitions = None
            if self._idc_page is IdcPage.OBJECTIVE:
                transitions = self._controller.structural_transition_journal
            text = render_idc(
                self._idc_page,
                frame=frame,
                transitions=transitions,
                feed_status=status,
                loop_timing=self.loop_timing,
                ingress_poll=self.ingress_poll,
                retention=self.retention_snapshot(),
            )
            self._display.render_frame(text)
            return text

        frame = self._controller.latest
        if frame.current_price is None:
            frame = self._controller.evaluate_now()
        self._publish_runtime(frame)
        status = self.feed_status()
        self._track_feed_transition(status)

        # H-7.2A: Mission Control is a passive view of the same latest frame.
        if self._mission_control and self._mc_shell is not None:
            from hotirjam_ai5.mission_control.runtime_bundle import (
                RuntimeBundle,
                read_lv_journal_summaries,
            )

            self._mc_shell.set_bundle(
                RuntimeBundle(
                    now=float(self._wall_clock()),
                    frame=frame,
                    loop_timing=self.loop_timing,
                    transition_summaries=read_lv_journal_summaries(self._controller),
                )
            )
            text = self._mc_shell.render(width=self._display.terminal_width())
            self._display.render_frame(text)
            return text

        market = MarketTelemetry(
            bid=self._last_bid,
            ask=self._last_ask,
            spread=self._last_spread,
            tick_rate=self._tick_rate(),
            latency_ms=self._last_latency_ms,
        )
        text = render_validator_frame(
            frame,
            developer_mode=self._developer_mode,
            feed_status=status,
            market=market,
            uptime_seconds=self.uptime_seconds(),
            audit=self._audit,
            terminal_width=self._display.terminal_width(),
            use_color=self._display.uses_ansi,
        )
        self._display.render_frame(text)
        return text

    _ESCAPE = "\x1b"
    _MAX_KEYS_PER_POLL = 32

    def _poll_keyboard_toggle(self) -> bool:
        """Drain pending keys for Dashboard / Developer View / IDC navigation.

        Non-blocking and cross-platform. Returns True when the view changed,
        so the caller can redraw immediately instead of waiting for the next
        refresh tick. Never restarts the runtime or touches engines.
        """
        changed = False
        for _ in range(self._MAX_KEYS_PER_POLL):
            ch = self._keyboard.poll_key()
            if ch is None:
                break
            if self._presentation_mode is PresentationMode.IDC:
                changed = self._handle_idc_key(ch) or changed
            elif ch in {"i", "I"}:
                changed = self.enter_idc() or changed
            elif ch in {"d", "D"}:
                self.toggle_developer_mode()
                changed = True
            elif self._mission_control and self._mc_shell is not None and ch in {
                "1",
                "2",
                "3",
                "j",
                "J",
                "k",
                "K",
                "e",
                "E",
                "\r",
                "\n",
                "?",
            }:
                self._mc_shell.handle_key(ch)
                changed = True
            elif ch == self._ESCAPE:
                changed = self.exit_developer_mode() or changed
        return changed

    def _handle_idc_key(self, ch: str) -> bool:
        """IDC navigation: page keys, Q back to menu or Dashboard."""
        if ch in {"q", "Q"}:
            if self._idc_page is IdcPage.MENU:
                return self.exit_idc()
            self._idc_page = IdcPage.MENU
            return True
        if self._idc_page is IdcPage.MENU:
            page = idc_page_for_key(ch)
            if page is not None:
                self._idc_page = page
                return True
        return False

    def run(self, *, max_frames: int | None = None) -> int:
        """Poll continuously; redraw on refresh cadence. Returns 0 on exit."""
        self._display.prepare()
        self._started_wall = self._wall_clock()
        self._audit.info("Validator started", timestamp=self._started_wall)
        frames = 0
        last_render_at: float | None = None
        self._keyboard.enable()
        try:
            while max_frames is None or frames < max_frames:
                try:
                    begin_loop_sample()
                except Exception:
                    pass

                _t0 = time.perf_counter()
                self.poll_once()
                try:
                    add_poll_ms((time.perf_counter() - _t0) * 1000.0)
                except Exception:
                    pass

                _t0 = time.perf_counter()
                view_changed = self._poll_keyboard_toggle()
                try:
                    add_keyboard_ms((time.perf_counter() - _t0) * 1000.0)
                except Exception:
                    pass

                now = self._clock()
                should_render = (
                    view_changed
                    or last_render_at is None
                    or (now - last_render_at) >= self._refresh_seconds
                )
                if should_render:
                    _t0 = time.perf_counter()
                    self.render_once()
                    try:
                        add_render_ms((time.perf_counter() - _t0) * 1000.0)
                    except Exception:
                        pass
                    last_render_at = now
                    frames += 1

                _t0 = time.perf_counter()
                self._sleep(self._poll_seconds)
                try:
                    add_sleep_ms((time.perf_counter() - _t0) * 1000.0)
                except Exception:
                    pass

                try:
                    finish_loop_sample()
                except Exception:
                    pass
        except KeyboardInterrupt:
            pass
        finally:
            self._keyboard.disable()
            self._display.shutdown()
        return 0


def _default_log_path() -> Path:
    return Path.cwd() / "logs" / "live_validator_snapshots.ndjson"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "HOTIRJAM AI 5 Live Validator — observation only. "
            "Runs Objective→Initiative→Response→Continuation→Break Capability. "
            "Decision and Execution are DISABLED. "
            "Press D for Developer View; Press I for Internal Diagnostics Console."
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
    parser.add_argument(
        "--mission-control",
        action="store_true",
        help=(
            "Optional passive Mission Control view (not the Objective live-validation "
            "watch window). Default is the classic Live Certification Dashboard "
            "(H-6.9.4-era). Prefer omitting this flag for Objective Engine validation."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    tick_path = args.tick_file or default_tick_path()
    dom_path = default_dom_path()
    log_path = args.log_file or _default_log_path()
    load_retention_config()

    logger = SnapshotLogger(log_path)
    from hotirjam_ai5.live_validator.candle_builder import TickBarBuilder
    from hotirjam_ai5.live_validator.swing_confirmer import SwingConfirmer

    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            tick_size=args.tick_size,
            symbol=args.symbol,
            hierarchy_checkpoint_path=log_path.with_name(
                f"{args.symbol.lower()}_structural_hierarchy.json"
            ),
            initiative_checkpoint_path=log_path.with_name(
                f"{args.symbol.lower()}_initiative_lifecycle.json"
            ),
        ),
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
        mission_control=bool(args.mission_control),
    )
    app.configure_retention_paths(
        tick_path=tick_path,
        dom_path=dom_path,
        snapshot_log_path=log_path,
    )
    if args.developer:
        app.toggle_developer_mode()
    return app.run(max_frames=args.max_frames)


if __name__ == "__main__":
    raise SystemExit(main())
