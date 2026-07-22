"""ANSI / VT fixed-viewport adapter."""

from __future__ import annotations

from typing import TextIO

from hotirjam_ai5.dashboard.display.adapter import Viewport
from hotirjam_ai5.dashboard.frame_buffer import FrameBuffer

_CLEAR_LINE = "\033[K"
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


class AnsiCursorAdapter:
    """Fixed viewport via cursor addressing. Line-diff when geometry stable."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._force_full = True

    def prepare(self, viewport: Viewport) -> None:
        del viewport
        self._force_full = True
        self._stream.write(_HIDE_CURSOR)
        self._stream.flush()

    def paint(
        self,
        frame: FrameBuffer,
        previous: FrameBuffer | None,
        viewport: Viewport,
    ) -> None:
        new_lines = _clamp_lines(frame.lines, viewport)
        old_lines: list[str] | None = None
        if not self._force_full and previous is not None:
            old_lines = list(_clamp_lines(previous.lines, viewport))

        row_count = max(len(new_lines), len(old_lines or []))
        for index in range(row_count):
            old = old_lines[index] if old_lines is not None and index < len(old_lines) else None
            new = new_lines[index] if index < len(new_lines) else ""
            if old == new and not self._force_full:
                continue
            row = index + 1
            self._stream.write(f"\033[{row};1H{_CLEAR_LINE}{new}")

        self._stream.flush()
        self._force_full = False

    def resize(self, viewport: Viewport) -> None:
        del viewport
        self._force_full = True

    def shutdown(self, viewport: Viewport) -> None:
        below = max(1, viewport.rows) + 1
        self._stream.write(f"\033[{below};1H{_SHOW_CURSOR}\n")
        self._stream.flush()


def _clamp_lines(lines: tuple[str, ...], viewport: Viewport) -> list[str]:
    cols = max(1, viewport.cols)
    rows = max(1, viewport.rows)
    return [line[:cols] for line in lines[:rows]]
