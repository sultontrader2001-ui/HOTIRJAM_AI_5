"""Cross-platform terminal helpers with safe ANSI or Windows fallback rendering."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from typing import TextIO

from hotirjam_ai5.dashboard.ansi_support import ansi_cursor_supported

# ANSI sequences — emitted only when VT/ANSI support is confirmed.
_CLEAR_LINE = "\033[K"
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"
_CLEAR_SCREEN = "\033[2J\033[H"
_STD_OUTPUT_HANDLE = -11


class TerminalDisplay:
    """Owns the dashboard region: one startup clear, then in-place updates."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        ansi_supported: bool | None = None,
        clear_command: Callable[[], None] | None = None,
    ) -> None:
        self._stream = stream or sys.stdout
        self._previous_lines: list[str] | None = None
        self._prepared = False
        self._clear_command = clear_command or _system_clear
        if ansi_supported is None:
            self._use_ansi = ansi_cursor_supported(self._stream)
        else:
            self._use_ansi = ansi_supported

    @property
    def uses_ansi(self) -> bool:
        """Whether this display emits ANSI cursor sequences."""
        return self._use_ansi

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    def write(self, text: str) -> None:
        """Write plain text and ensure a trailing newline."""
        self._stream.write(text)
        if not text.endswith("\n"):
            self._stream.write("\n")
        self._stream.flush()

    def prepare(self) -> None:
        """Clear the terminal exactly once and reserve the dashboard area."""
        self._previous_lines = None
        self._clear_screen_once()
        if self._use_ansi:
            self._stream.write(_HIDE_CURSOR)
            self._stream.flush()
        self._prepared = True

    def shutdown(self) -> None:
        """Restore cursor and leave the terminal usable after exit."""
        lines = self._previous_lines or []
        if self._use_ansi:
            below = len(lines) + 1
            self._stream.write(f"\033[{below};1H{_SHOW_CURSOR}\n")
            self._stream.flush()
        elif self._is_interactive_console():
            self.write("")
        self._previous_lines = None
        self._prepared = False

    def render_frame(self, text: str, *, clear: bool = False) -> None:
        """Update only the dashboard lines. Never clears the full screen here."""
        del clear
        new_lines = text.splitlines()
        if self._previous_lines is not None and new_lines == self._previous_lines:
            return

        if self._use_ansi:
            self._render_ansi_diff(new_lines)
        else:
            self._render_compatible(new_lines)

        self._previous_lines = list(new_lines)

    def reset(self) -> None:
        """Alias for shutdown used by older call sites."""
        self.shutdown()

    def _clear_screen_once(self) -> None:
        """Startup-only clear: ``cls`` / ``clear``, or ANSI when VT is active."""
        if self._is_interactive_console():
            self._clear_command()
            return
        if self._use_ansi:
            self._stream.write(_CLEAR_SCREEN)
            self._stream.flush()

    def _render_ansi_diff(self, new_lines: list[str]) -> None:
        old_lines = self._previous_lines or []
        max_count = max(len(old_lines), len(new_lines))
        for index in range(max_count):
            old = old_lines[index] if index < len(old_lines) else None
            new = new_lines[index] if index < len(new_lines) else ""
            if old == new:
                continue
            row = index + 1
            self._stream.write(f"\033[{row};1H{_CLEAR_LINE}{new}")
        self._stream.flush()

    def _render_compatible(self, new_lines: list[str]) -> None:
        """Overwrite the dashboard region without printing ANSI escapes."""
        if not self._is_interactive_console():
            self._stream.write("\n".join(new_lines) + "\n")
            self._stream.flush()
            return

        width = self._terminal_width()
        if self._is_windows_console():
            _windows_set_cursor_home()

        for line in new_lines:
            padded = line[:width].ljust(width)
            self._stream.write(padded + "\n")

        old_count = len(self._previous_lines or [])
        for _ in range(max(0, old_count - len(new_lines))):
            self._stream.write(" " * width + "\n")
        self._stream.flush()

        if self._is_windows_console():
            _windows_set_cursor_home()

    def terminal_width(self) -> int:
        """Current terminal column count for layout decisions."""
        return self._terminal_width()

    def _terminal_width(self) -> int:
        try:
            return max(40, shutil.get_terminal_size(fallback=(80, 24)).columns)
        except OSError:
            return 80

    def _is_interactive_console(self) -> bool:
        if self._stream is not sys.stdout and self._stream is not sys.stderr:
            return False
        isatty = getattr(self._stream, "isatty", None)
        return bool(isatty and isatty())

    def _is_windows_console(self) -> bool:
        return os.name == "nt" and self._is_interactive_console()


def _system_clear() -> None:
    """Platform clear used exactly once at dashboard startup."""
    os.system("cls" if os.name == "nt" else "clear")


def _windows_set_cursor_home() -> bool:
    """Move the Windows console cursor to (0, 0) without printing escapes."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class _Coord(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        if handle in (0, -1):
            return False
        return bool(kernel32.SetConsoleCursorPosition(handle, _Coord(0, 0)))
    except (AttributeError, OSError, ValueError):
        return False
