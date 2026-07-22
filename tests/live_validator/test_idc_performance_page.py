"""H-6.6.5 IDC Performance page — render existing LoopTimingSnapshot only."""

from __future__ import annotations

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    IdcPage,
    LiveValidatorApp,
    LiveValidatorController,
    LoopTimingSnapshot,
    PresentationMode,
    TimingSeverity,
    render_idc,
)
from hotirjam_ai5.live_validator.idc_performance import render_performance_page
from hotirjam_ai5.live_validator.loop_timing import reset_loop_timing_for_tests


def _tick(price: float, *, ts: float) -> LiveTick:
    return LiveTick(
        timestamp=ts,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=1.0,
    )


class _FakeKeyboard:
    def __init__(self, batches: list[str] | None = None) -> None:
        self._batches = list(batches or [])
        self._pending: list[str] = list(self._batches.pop(0)) if self._batches else []

    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        if self._pending:
            return self._pending.pop(0)
        if self._batches:
            self._pending = list(self._batches.pop(0))
        return None


def _snap(
    *,
    poll_ms: float = 1.0,
    poll_severity: TimingSeverity = TimingSeverity.OK,
    keyboard_ms: float = 0.5,
    render_ms: float = 2.0,
    sleep_ms: float = 10.0,
    initiative_checkpoint_ms: float = 0.0,
    hierarchy_checkpoint_ms: float = 0.0,
    logging_ms: float = 0.0,
    loop_ms: float = 15.0,
) -> LoopTimingSnapshot:
    checkpoint_ms = initiative_checkpoint_ms + hierarchy_checkpoint_ms
    return LoopTimingSnapshot(
        loop_ms=loop_ms,
        poll_ms=poll_ms,
        keyboard_ms=keyboard_ms,
        render_ms=render_ms,
        sleep_ms=sleep_ms,
        checkpoint_ms=checkpoint_ms,
        initiative_checkpoint_ms=initiative_checkpoint_ms,
        hierarchy_checkpoint_ms=hierarchy_checkpoint_ms,
        logging_ms=logging_ms,
        start_time=100.0,
        end_time=100.015,
        poll_severity=poll_severity,
        keyboard_severity=TimingSeverity.OK,
        render_severity=TimingSeverity.OK,
        sleep_severity=TimingSeverity.OK,
        checkpoint_severity=TimingSeverity.OK
        if checkpoint_ms < 100
        else TimingSeverity.SLOW,
        initiative_checkpoint_severity=TimingSeverity.OK,
        hierarchy_checkpoint_severity=TimingSeverity.OK,
        logging_severity=TimingSeverity.OK,
        loop_severity=TimingSeverity.OK if loop_ms < 100 else TimingSeverity.SLOW,
    )


def test_performance_page_layout_with_snapshot() -> None:
    text = render_performance_page(_snap(), feed_status="LIVE")
    for section in (
        "PERFORMANCE",
        "FEED INGRESS (TEMPORARY)",
        "RETENTION",
        "Current Journal Entries",
        "Gate",
        "tail_lines",
        "accepted_count",
        "skipped_count",
        "Status",
        "Health",
        "Last Sample",
        "MAIN LOOP",
        "Loop Time",
        "PIPELINE",
        "poll_once()",
        "KEYBOARD",
        "Keyboard Poll",
        "RENDER",
        "render_once()",
        "CHECKPOINTS",
        "Initiative Checkpoint",
        "Hierarchy Checkpoint",
        "Combined Checkpoint",
        "Snapshot Logger",
        "SLEEP",
        "Sleep Time",
        "SUMMARY",
        "Longest Stage",
        "Longest Duration",
        "Overall Status",
        "WARNINGS",
        "Press Q to return",
    ):
        assert section in text
    assert "LIVE" in text
    assert "OK" in text
    assert "Collect........." in text
    assert "Assemble........" in text
    assert "Rotate.........." in text
    assert "Reopen.........." in text
    assert "fsync..........." in text
    assert "os.replace......" in text
    assert "Tick Retention" in text
    assert "read retained..." in text
    assert "IMPLEMENTATION PENDING" not in text


def test_unavailable_timing_shows_not_available() -> None:
    text = render_performance_page(None)
    assert "NOT AVAILABLE" in text
    assert "FEED INGRESS (TEMPORARY)" in text
    assert "IMPLEMENTATION PENDING" not in text


def test_performance_page_shows_ingress_poll_snapshot() -> None:
    from hotirjam_ai5.live_data.ingress_poll_snapshot import IngressPollSnapshot

    snap = IngressPollSnapshot(
        tail_lines=0,
        accepted_count=0,
        skipped_count=0,
        accepted_delta=0,
        skipped_delta=0,
        file_offset=4096,
        file_size=4096,
    )
    text = render_performance_page(None, feed_status="WAITING", ingress_poll=snap)
    assert "Gate              A_ZERO_TAIL_LINES" in text
    assert "tail_lines        0" in text
    assert "accepted_count    0" in text
    assert "skipped_count     0" in text
    assert "file_offset       4096" in text
    assert "file_size         4096" in text


def test_warnings_only_from_existing_severities() -> None:
    snap = LoopTimingSnapshot(
        loop_ms=150.0,
        poll_ms=150.0,
        keyboard_ms=0.5,
        render_ms=2.0,
        sleep_ms=10.0,
        checkpoint_ms=0.0,
        initiative_checkpoint_ms=0.0,
        hierarchy_checkpoint_ms=0.0,
        logging_ms=0.0,
        start_time=1.0,
        end_time=1.15,
        poll_severity=TimingSeverity.SLOW,
        keyboard_severity=TimingSeverity.OK,
        render_severity=TimingSeverity.OK,
        sleep_severity=TimingSeverity.OK,
        checkpoint_severity=TimingSeverity.OK,
        initiative_checkpoint_severity=TimingSeverity.OK,
        hierarchy_checkpoint_severity=TimingSeverity.OK,
        logging_severity=TimingSeverity.OK,
        loop_severity=TimingSeverity.SLOW,
    )
    text = render_performance_page(snap)
    warn = text.split("WARNINGS", 1)[1]
    assert "SLOW  poll_once()" in warn
    assert "SLOW  Loop Time" in warn
    assert "CRITICAL" not in warn



def test_acceptance_path_performance_page() -> None:
    """Dashboard → I → 9 → Performance → Q → IDC → Q → Dashboard."""
    reset_loop_timing_for_tests()
    LiveValidatorApp(
        controller=LiveValidatorController(),
        keyboard=_FakeKeyboard([]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    ).run(max_frames=1)

    app = LiveValidatorApp(
        controller=LiveValidatorController(),
        keyboard=_FakeKeyboard(["I", "9", "Q", "Q"]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app._poll_keyboard_toggle()
    app._poll_keyboard_toggle()
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.PERFORMANCE
    text = app.render_once()
    assert "PERFORMANCE" in text
    assert "MAIN LOOP" in text
    assert "IMPLEMENTATION PENDING" not in text
    assert "NOT AVAILABLE" not in text.split("Loop Time", 1)[1].split("Status", 1)[0]
    app._poll_keyboard_toggle()
    assert app.idc_page is IdcPage.MENU
    app._poll_keyboard_toggle()
    assert app.presentation_mode is PresentationMode.DASHBOARD


def test_live_feed_continues_on_performance_page() -> None:
    class FakeIngress:
        def __init__(self) -> None:
            self._ts = 0.0

        def poll(self) -> tuple[LiveTick, ...]:
            self._ts += 1.0
            return (_tick(100.0 + self._ts * 0.25, ts=self._ts),)

    reset_loop_timing_for_tests()
    controller = LiveValidatorController()
    app = LiveValidatorApp(
        controller=controller,
        ingress=FakeIngress(),  # type: ignore[arg-type]
        keyboard=_FakeKeyboard(["", "I", "9", "", ""]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app.run(max_frames=5)
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.PERFORMANCE
    assert app.feed_status() in {"LIVE", "STALE"}
    assert controller.evaluations >= 1
    assert app.loop_timing is not None


def test_render_idc_dispatches_performance() -> None:
    text = render_idc(IdcPage.PERFORMANCE, loop_timing=_snap(), feed_status="LIVE")
    assert "poll_once()" in text
    assert "1.00 ms" in text
