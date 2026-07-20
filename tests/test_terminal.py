"""Tests for TerminalDisplay diff rendering."""

from __future__ import annotations

import io

from hotirjam_ai5.dashboard.terminal import TerminalDisplay


class _AnsiStream(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_write_appends_newline_when_missing() -> None:
    buffer = io.StringIO()
    TerminalDisplay(stream=buffer).write("hello")
    assert buffer.getvalue() == "hello\n"


def test_non_tty_skips_unchanged_frame() -> None:
    buffer = io.StringIO()
    display = TerminalDisplay(stream=buffer)
    display.render_frame("line-a\nline-b")
    display.render_frame("line-a\nline-b")
    assert buffer.getvalue().count("line-a") == 1


def test_non_tty_rewrites_when_content_changes() -> None:
    buffer = io.StringIO()
    display = TerminalDisplay(stream=buffer)
    display.render_frame("one")
    display.render_frame("two")
    assert "one" in buffer.getvalue()
    assert "two" in buffer.getvalue()


def test_ansi_diff_rewrites_only_changed_line() -> None:
    buffer = _AnsiStream()
    display = TerminalDisplay(stream=buffer)
    display.render_frame("A\nB\nC")
    first = buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    display.render_frame("A\nX\nC")
    second = buffer.getvalue()
    assert "\033[2;1H" in second
    assert "X" in second
    # Unchanged row 1 should not be repositioned on the second paint.
    assert "\033[1;1H" not in second
    assert first  # first paint occurred


def test_ansi_does_not_full_screen_clear() -> None:
    buffer = _AnsiStream()
    display = TerminalDisplay(stream=buffer)
    display.render_frame("hello")
    assert "\033[2J" not in buffer.getvalue()
