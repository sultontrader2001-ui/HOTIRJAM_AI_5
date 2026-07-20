"""Cross-platform terminal helpers with safe ANSI or Windows fallback rendering."""

from __future__ import annotations

import os
import sys
from typing import TextIO

from hotirjam_ai5.dashboard.ansi_support import ansi_cursor_supported

# ANSI: cursor home, clear line, hide/show cursor (only when VT/ANSI is confirmed).
_CLEAR_LINE = "\033[K"
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


class TerminalDisplay:
    """Renders dashboard frames with ANSI diff, or a plain Windows-safe fallback."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        ansi_supported: bool | None = None,
    ) -> None:
        self._stream = stream or sys.stdout
        self._previous_lines: list[str] | None = None
        if ansi_supported is None:
            self._use_ansi = ansi_cursor_supported(self._stream)
        else:
            self._use_ansi = ansi_supported

    @property
    def uses_ansi(self) -> bool:
        """Whether this display emits ANSI cursor sequences."""
        return self._use_ansi

    def write(self, text: str) -> None:
        """Write plain text and ensure a trailing newline."""
        self._stream.write(text)
        if not text.endswith("\n"):
            self._stream.write("\n")
        self._stream.flush()

    def render_frame(self, text: str, *, clear: bool = False) -> None:
        """Update the dashboard. Never emits ANSI when unsupported."""
        del clear
        new_lines = text.splitlines()
        if self._previous_lines is not None and new_lines == self._previous_lines:
            return

        if self._use_ansi:
            self._render_ansi_diff(new_lines)
        else:
            self._render_compatible(text)

        self._previous_lines = list(new_lines)

    def _render_ansi_diff(self, new_lines: list[str]) -> None:
        old_lines = self._previous_lines or []
        self._stream.write(_HIDE_CURSOR)

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

    def _render_compatible(self, text: str) -> None:
        """Full redraw without ANSI escapes (Windows PowerShell-safe)."""
        frame = text if text.endswith("\n") else f"{text}\n"
        if self._is_windows_console():
            # Compatible clear — no VT sequences printed to the screen.
            os.system("cls")
        self._stream.write(frame)
        self._stream.flush()

    def _is_windows_console(self) -> bool:
        if os.name != "nt":
            return False
        if self._stream is not sys.stdout and self._stream is not sys.stderr:
            return False
        isatty = getattr(self._stream, "isatty", None)
        return bool(isatty and isatty())

    def reset(self) -> None:
        """Forget prior frame state (next render paints from scratch)."""
        self._previous_lines = None
        if self._use_ansi:
            self._stream.write(_SHOW_CURSOR)
            self._stream.flush()
