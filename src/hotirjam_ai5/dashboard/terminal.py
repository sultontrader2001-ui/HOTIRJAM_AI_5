"""Cross-platform terminal helpers with flicker-free diff rendering."""

from __future__ import annotations

import sys
from typing import TextIO

# ANSI: cursor home, clear line, hide/show cursor (no full-screen clear).
_CURSOR_HOME = "\033[H"
_CLEAR_LINE = "\033[K"
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


class TerminalDisplay:
    """Renders dashboard frames by rewriting only changed lines in place."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout
        self._previous_lines: list[str] | None = None
        self._use_ansi = self._detect_ansi(self._stream)

    @staticmethod
    def _detect_ansi(stream: TextIO) -> bool:
        if stream is sys.stdout or stream is sys.stderr:
            return True
        isatty = getattr(stream, "isatty", None)
        return bool(isatty and isatty())

    def write(self, text: str) -> None:
        """Write text and ensure a trailing newline."""
        self._stream.write(text)
        if not text.endswith("\n"):
            self._stream.write("\n")
        self._stream.flush()

    def render_frame(self, text: str, *, clear: bool = False) -> None:
        """Update the visible dashboard without clearing the whole screen.

        ``clear`` is accepted for compatibility but ignored — full-screen clear
        causes flicker and is intentionally not used.
        """
        del clear
        new_lines = text.splitlines()
        if self._previous_lines is not None and new_lines == self._previous_lines:
            return

        if self._use_ansi:
            self._render_diff(new_lines)
        else:
            # Non-TTY (tests/pipes): write a full frame only when content changes.
            self.write(text if text.endswith("\n") else text + "\n")

        self._previous_lines = list(new_lines)

    def _render_diff(self, new_lines: list[str]) -> None:
        old_lines = self._previous_lines or []
        self._stream.write(_HIDE_CURSOR)
        if self._previous_lines is None:
            self._stream.write(_CURSOR_HOME)

        max_count = max(len(old_lines), len(new_lines))
        for index in range(max_count):
            old = old_lines[index] if index < len(old_lines) else None
            new = new_lines[index] if index < len(new_lines) else ""
            if old == new:
                continue
            row = index + 1
            self._stream.write(f"\033[{row};1H{_CLEAR_LINE}{new}")

        self._stream.write(_SHOW_CURSOR)
        self._stream.flush()

    def reset(self) -> None:
        """Forget prior frame state (next render paints from scratch)."""
        self._previous_lines = None
        if self._use_ansi:
            self._stream.write(_SHOW_CURSOR)
            self._stream.flush()
