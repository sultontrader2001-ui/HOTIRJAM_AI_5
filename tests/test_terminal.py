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


def test_prepare_clears_terminal_exactly_once() -> None:
    clears: list[int] = []
    buffer = io.StringIO()
    display = TerminalDisplay(
        stream=buffer,
        ansi_supported=False,
        clear_command=lambda: clears.append(1),
    )
    # Non-interactive stream skips os clear; force path via interactive mock.
    display._is_interactive_console = lambda: True  # type: ignore[method-assign]
    display.prepare()
    display.render_frame("A")
    display.render_frame("B")
    assert clears == [1]
    assert display.is_prepared is True


def test_shutdown_restores_cursor_when_ansi() -> None:
    buffer = _TtyStream()
    display = TerminalDisplay(stream=buffer, ansi_supported=True, clear_command=lambda: None)
    display.prepare()
    display.render_frame("line1\nline2")
    buffer.seek(0)
    buffer.truncate(0)
    display.shutdown()
    output = buffer.getvalue()
    assert "\033[?25h" in output
    assert display.is_prepared is False


def test_render_frame_never_full_clears_after_prepare() -> None:
    clears: list[int] = []
    buffer = io.StringIO()
    display = TerminalDisplay(
        stream=buffer,
        ansi_supported=False,
        clear_command=lambda: clears.append(1),
    )
    display._is_interactive_console = lambda: True  # type: ignore[method-assign]
    display.prepare()
    assert clears == [1]
    display.render_frame("one")
    display.render_frame("two")
    assert clears == [1]


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
    display = TerminalDisplay(
        stream=buffer,
        ansi_supported=True,
        clear_command=lambda: None,
    )
    display.prepare()
    display.render_frame("A\nB\nC")
    buffer.seek(0)
    buffer.truncate(0)
    display.render_frame("A\nX\nC")
    second = buffer.getvalue()
    assert "\033[2;1H" in second
    assert "X" in second
    assert "\033[1;1H" not in second
    assert "\033[2J" not in second


def test_ansi_mode_does_not_full_screen_clear_on_refresh() -> None:
    buffer = _TtyStream()
    display = TerminalDisplay(
        stream=buffer,
        ansi_supported=True,
        clear_command=lambda: None,
    )
    display.prepare()
    buffer.seek(0)
    buffer.truncate(0)
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
