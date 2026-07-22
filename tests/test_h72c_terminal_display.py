"""H-7.2C Terminal Display certification — FrameBuffer + adapters + facade."""

from __future__ import annotations

import io

from hotirjam_ai5.dashboard.display import (
    AnsiCursorAdapter,
    CaptureAdapter,
    CompatibleHomeAdapter,
    Viewport,
)
from hotirjam_ai5.dashboard.frame_buffer import FrameBuffer
from hotirjam_ai5.dashboard.terminal import TerminalDisplay


class _TtyStream(io.StringIO):
    def isatty(self) -> bool:
        return True


class _NonSeekable:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, s: str) -> int:
        self.writes.append(s)
        return len(s)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def test_framebuffer_is_immutable_and_has_identity() -> None:
    frame = FrameBuffer.from_text("a\nb", width=40, height=2, timestamp=1.0)
    assert frame.lines == ("a", "b")
    assert frame.width == 40
    assert frame.height == 2
    assert frame.identity
    assert frame.timestamp == 1.0
    twin = FrameBuffer.from_text("a\nb", timestamp=2.0)
    assert frame.same_content(twin)
    assert frame.same_for_skip(twin)


def test_facade_selects_capture_for_non_tty() -> None:
    display = TerminalDisplay(stream=io.StringIO(), ansi_supported=False)
    assert display.adapter_name == "CaptureAdapter"


def test_facade_selects_compatible_for_tty_without_ansi() -> None:
    display = TerminalDisplay(stream=_TtyStream(), ansi_supported=False)
    assert display.adapter_name == "CompatibleHomeAdapter"


def test_facade_selects_ansi_for_tty_with_ansi() -> None:
    display = TerminalDisplay(stream=_TtyStream(), ansi_supported=True)
    assert display.adapter_name == "AnsiCursorAdapter"


def test_capture_adapter_replace_not_append() -> None:
    stream = io.StringIO()
    adapter = CaptureAdapter(stream)
    viewport = Viewport(rows=24, cols=80)
    adapter.prepare(viewport)
    f1 = FrameBuffer.from_text("one\ntwo")
    f2 = FrameBuffer.from_text("three")
    adapter.paint(f1, None, viewport)
    adapter.paint(f2, f1, viewport)
    assert stream.getvalue() == "three\n"
    assert adapter.paint_count == 2
    assert adapter.last_frame == f2
    assert len(adapter.painted_frames) == 2


def test_capture_adapter_snapshot_on_non_seekable() -> None:
    stream = _NonSeekable()
    adapter = CaptureAdapter(stream)  # type: ignore[arg-type]
    viewport = Viewport(rows=10, cols=40)
    adapter.prepare(viewport)
    adapter.paint(FrameBuffer.from_text("first"), None, viewport)
    adapter.paint(FrameBuffer.from_text("second"), None, viewport)
    joined = "".join(stream.writes)
    assert joined.count("first") == 1
    assert "second" not in joined  # snapshot — no append


def test_compatible_home_never_appends_on_seekable_tty() -> None:
    stream = _TtyStream()
    adapter = CompatibleHomeAdapter(stream)
    viewport = Viewport(rows=10, cols=40)
    adapter.prepare(viewport)
    assert adapter.mode == "replace"
    adapter.paint(FrameBuffer.from_text("alpha"), None, viewport)
    adapter.paint(FrameBuffer.from_text("beta"), None, viewport)
    assert stream.getvalue().strip() == "beta"
    assert "alpha" not in stream.getvalue()


def test_compatible_snapshot_mode_no_scroll() -> None:
    stream = _NonSeekable()
    adapter = CompatibleHomeAdapter(stream)  # type: ignore[arg-type]
    viewport = Viewport(rows=5, cols=20)
    adapter.prepare(viewport)
    assert adapter.mode == "snapshot"
    adapter.paint(FrameBuffer.from_text("one"), None, viewport)
    adapter.paint(FrameBuffer.from_text("two"), None, viewport)
    joined = "".join(stream.writes)
    assert "one" in joined
    assert "two" not in joined


def test_facade_skips_identical_identity_and_content() -> None:
    display = TerminalDisplay(stream=io.StringIO(), ansi_supported=False)
    a = FrameBuffer.from_text("x", identity="same", timestamp=1.0)
    b = FrameBuffer.from_text("x", identity="same", timestamp=2.0)
    c = FrameBuffer.from_text("x", identity="other", timestamp=3.0)
    display.paint(a)
    display.paint(b)
    display.paint(c)
    assert display.paint_count == 1
    assert display.skip_count == 2


def test_facade_single_paint_per_changed_refresh() -> None:
    display = TerminalDisplay(stream=io.StringIO(), ansi_supported=False)
    display.render_frame("A")
    display.render_frame("B")
    display.render_frame("B")
    assert display.paint_count == 2
    assert display.skip_count == 1


def test_no_duplicated_rows_across_refreshes() -> None:
    buffer = io.StringIO()
    display = TerminalDisplay(stream=buffer, ansi_supported=False)
    frame = "r1\nr2\nr3"
    for _ in range(20):
        display.render_frame(frame)
    assert buffer.getvalue() == "r1\nr2\nr3\n"
    assert display.paint_count == 1


def test_ansi_adapter_line_diff() -> None:
    stream = _TtyStream()
    adapter = AnsiCursorAdapter(stream)
    viewport = Viewport(rows=24, cols=80)
    adapter.prepare(viewport)
    stream.seek(0)
    stream.truncate(0)
    f1 = FrameBuffer.from_text("A\nB\nC")
    f2 = FrameBuffer.from_text("A\nX\nC")
    adapter.paint(f1, None, viewport)
    stream.seek(0)
    stream.truncate(0)
    adapter.paint(f2, f1, viewport)
    out = stream.getvalue()
    assert "\033[2;1H" in out
    assert "\033[1;1H" not in out


def test_resize_invalidates_and_forces_paint() -> None:
    display = TerminalDisplay(stream=io.StringIO(), ansi_supported=False)
    display.render_frame("same")
    assert display.paint_count == 1
    display._viewport = Viewport(rows=10, cols=40)
    display._adapter.resize(display._viewport)
    display._last_frame = None
    display.render_frame("same")
    assert display.paint_count == 2
