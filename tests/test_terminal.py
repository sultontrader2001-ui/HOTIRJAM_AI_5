"""Tests for TerminalDisplay."""

from __future__ import annotations

import io

from hotirjam_ai5.dashboard.terminal import TerminalDisplay


def test_write_appends_newline_when_missing() -> None:
    buffer = io.StringIO()
    TerminalDisplay(stream=buffer).write("hello")
    assert buffer.getvalue() == "hello\n"


def test_render_frame_without_clear_writes_text() -> None:
    buffer = io.StringIO()
    TerminalDisplay(stream=buffer).render_frame("frame", clear=False)
    assert buffer.getvalue() == "frame\n"


def test_clear_on_non_stdout_is_noop() -> None:
    buffer = io.StringIO()
    display = TerminalDisplay(stream=buffer)
    display.clear()
    assert buffer.getvalue() == ""
