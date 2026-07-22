"""TerminalDisplay facade — FrameBuffer + DisplayAdapter orchestration (H-7.2C)."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from typing import TextIO

from hotirjam_ai5.dashboard.ansi_support import ansi_cursor_supported
from hotirjam_ai5.dashboard.display.adapter import DisplayAdapter, Viewport
from hotirjam_ai5.dashboard.display.ansi_cursor import AnsiCursorAdapter
from hotirjam_ai5.dashboard.display.capture import CaptureAdapter
from hotirjam_ai5.dashboard.display.compatible_home import CompatibleHomeAdapter
from hotirjam_ai5.dashboard.frame_buffer import FrameBuffer

_CLEAR_SCREEN = "\033[2J\033[H"


class TerminalDisplay:
    """Facade: prepare → select adapter → skip identical → paint once → shutdown."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        ansi_supported: bool | None = None,
        clear_command: Callable[[], None] | None = None,
        adapter: DisplayAdapter | None = None,
    ) -> None:
        self._stream = stream or sys.stdout
        self._clear_command = clear_command or _system_clear
        self._prepared = False
        self._last_frame: FrameBuffer | None = None
        self._paint_count = 0
        self._skip_count = 0
        self._viewport = self._read_viewport()

        if ansi_supported is None:
            self._use_ansi = ansi_cursor_supported(self._stream)
        else:
            self._use_ansi = ansi_supported

        if adapter is not None:
            self._adapter: DisplayAdapter = adapter
        else:
            self._adapter = self._select_adapter()

    @property
    def uses_ansi(self) -> bool:
        return self._use_ansi and isinstance(self._adapter, AnsiCursorAdapter)

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    @property
    def paint_count(self) -> int:
        """Adapter paint invocations (identical skips excluded)."""
        return self._paint_count

    @property
    def skip_count(self) -> int:
        return self._skip_count

    @property
    def last_frame(self) -> FrameBuffer | None:
        return self._last_frame

    @property
    def adapter_name(self) -> str:
        return type(self._adapter).__name__

    def write(self, text: str) -> None:
        """Write plain text and ensure a trailing newline (non-frame helper)."""
        self._stream.write(text)
        if not text.endswith("\n"):
            self._stream.write("\n")
        self._stream.flush()

    def prepare(self) -> None:
        """Clear once and prepare the selected adapter."""
        self._last_frame = None
        self._viewport = self._read_viewport()
        self._clear_screen_once()
        self._adapter.prepare(self._viewport)
        self._prepared = True

    def shutdown(self) -> None:
        """Restore terminal after the display session."""
        viewport = self._viewport_for_shutdown()
        self._adapter.shutdown(viewport)
        self._last_frame = None
        self._prepared = False

    def reset(self) -> None:
        self.shutdown()

    def paint(self, frame: FrameBuffer) -> None:
        """Single paint pass. Skips when identity or content is unchanged."""
        self._sync_viewport()
        if self._last_frame is not None and frame.same_for_skip(self._last_frame):
            self._skip_count += 1
            return
        previous = self._last_frame
        self._adapter.paint(frame, previous, self._viewport)
        self._last_frame = frame
        self._paint_count += 1

    def render_frame(self, text: str, *, clear: bool = False) -> None:
        """Migration sugar: compose FrameBuffer from text, then paint once."""
        del clear
        width = self.terminal_width()
        frame = FrameBuffer.from_text(text, width=width)
        self.paint(frame)

    def terminal_width(self) -> int:
        return self._viewport.cols

    def terminal_height(self) -> int:
        return self._viewport.rows

    def _select_adapter(self) -> DisplayAdapter:
        if self._use_ansi:
            return AnsiCursorAdapter(self._stream)
        if _is_tty(self._stream):
            return CompatibleHomeAdapter(self._stream)
        return CaptureAdapter(self._stream)

    def _sync_viewport(self) -> None:
        current = self._read_viewport()
        if current != self._viewport:
            self._viewport = current
            self._adapter.resize(current)
            self._last_frame = None

    def _read_viewport(self) -> Viewport:
        try:
            size = shutil.get_terminal_size(fallback=(80, 24))
            cols = max(40, size.columns)
            rows = max(1, size.lines)
        except OSError:
            cols, rows = 80, 24
        return Viewport(rows=rows, cols=cols)

    def _viewport_for_shutdown(self) -> Viewport:
        if self._last_frame is not None:
            rows = max(1, len(self._last_frame.lines))
            return Viewport(rows=rows, cols=self._viewport.cols)
        return self._viewport

    def _clear_screen_once(self) -> None:
        if self._is_interactive_console():
            self._clear_command()
            return
        if self._use_ansi:
            self._stream.write(_CLEAR_SCREEN)
            self._stream.flush()

    def _is_interactive_console(self) -> bool:
        if self._stream is not sys.stdout and self._stream is not sys.stderr:
            return False
        return _is_tty(self._stream)


def _system_clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())
