"""Cross-platform terminal helpers for dashboard refresh."""

from __future__ import annotations

import os
import sys
from typing import TextIO


class TerminalDisplay:
    """Writes dashboard frames to a text stream with optional clear."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def clear(self) -> None:
        """Clear the visible terminal screen (ANSI + Windows fallback)."""
        if self._stream is not sys.stdout and self._stream is not sys.stderr:
            return
        if os.name == "nt":
            os.system("cls")
        else:
            self._stream.write("\033[2J\033[H")
            self._stream.flush()

    def write(self, text: str) -> None:
        """Write one full dashboard frame."""
        self._stream.write(text)
        if not text.endswith("\n"):
            self._stream.write("\n")
        self._stream.flush()

    def render_frame(self, text: str, *, clear: bool = True) -> None:
        """Optionally clear, then write one frame."""
        if clear:
            self.clear()
        self.write(text)
