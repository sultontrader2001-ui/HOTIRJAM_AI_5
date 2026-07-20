"""Tests for TerminalDisplay and ANSI capability detection."""

from __future__ import annotations

import io

import pytest

from hotirjam_ai5.dashboard import ansi_support
from hotirjam_ai5.dashboard.terminal import TerminalDisplay


class _TtyStream(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_write_appends_newline_when_missing() -> None:
    buffer = io.StringIO()
    TerminalDisplay(stream=buffer, ansi_supported=False).write("hello")
    assert buffer.getvalue() == "hello\n"


def test_non_tty_skips_unchanged_frame() -> None:
    buffer = io.StringIO()
    display = TerminalDisplay(stream=buffer, ansi_supported=False)
    display.render_frame("line-a\nline-b")
    display.render_frame("line-a\nline-b")
    assert buffer.getvalue().count("line-a") == 1


def test_non_tty_rewrites_when_content_changes() -> None:
    buffer = io.StringIO()
    display = TerminalDisplay(stream=buffer, ansi_supported=False)
    display.render_frame("one")
    display.render_frame("two")
    assert "one" in buffer.getvalue()
    assert "two" in buffer.getvalue()


def test_ansi_diff_rewrites_only_changed_line() -> None:
    buffer = _TtyStream()
    display = TerminalDisplay(stream=buffer, ansi_supported=True)
    display.render_frame("A\nB\nC")
    buffer.seek(0)
    buffer.truncate(0)
    display.render_frame("A\nX\nC")
    second = buffer.getvalue()
    assert "\033[2;1H" in second
    assert "X" in second
    assert "\033[1;1H" not in second


def test_ansi_mode_does_not_full_screen_clear_sequence() -> None:
    buffer = _TtyStream()
    display = TerminalDisplay(stream=buffer, ansi_supported=True)
    display.render_frame("hello")
    assert "\033[2J" not in buffer.getvalue()


def test_fallback_never_emits_raw_ansi_escape_sequences() -> None:
    """Regression: Windows PowerShell without VT must not print [1;1H / [K / [25l."""
    buffer = _TtyStream()
    display = TerminalDisplay(stream=buffer, ansi_supported=False)
    assert display.uses_ansi is False
    display.render_frame("HOTIRJAM AI 5\nSYSTEM\n- Engine Status: RUNNING")
    display.render_frame("HOTIRJAM AI 5\nSYSTEM\n- Engine Status: STOPPED")
    output = buffer.getvalue()
    assert "\033" not in output
    assert "[1;1H" not in output
    assert "[K" not in output
    assert "[?25l" not in output
    assert "[?25h" not in output
    assert "HOTIRJAM AI 5" in output
    assert "STOPPED" in output


def test_tty_alone_does_not_force_ansi_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ansi_support.os, "name", "nt")
    monkeypatch.delenv("HOTIRJAM_FORCE_ANSI", raising=False)
    monkeypatch.setattr(ansi_support, "_windows_vt_enabled", lambda _stream: False)
    stream = _TtyStream()
    assert ansi_support.ansi_cursor_supported(stream) is False
    display = TerminalDisplay(stream=stream)
    assert display.uses_ansi is False
    display.render_frame("plain")
    assert "\033" not in stream.getvalue()


def test_force_ansi_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTIRJAM_FORCE_ANSI", "0")
    assert ansi_support.ansi_cursor_supported(_TtyStream()) is False
    monkeypatch.setenv("HOTIRJAM_FORCE_ANSI", "1")
    assert ansi_support.ansi_cursor_supported(_TtyStream()) is True


def test_non_tty_stream_reports_no_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOTIRJAM_FORCE_ANSI", raising=False)
    assert ansi_support.ansi_cursor_supported(io.StringIO()) is False
