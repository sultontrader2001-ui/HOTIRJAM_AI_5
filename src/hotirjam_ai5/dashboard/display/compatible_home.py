"""Interactive non-ANSI fixed-viewport adapter (never appends)."""

from __future__ import annotations

import io
import os
from typing import TextIO

from hotirjam_ai5.dashboard.display.adapter import Viewport
from hotirjam_ai5.dashboard.frame_buffer import FrameBuffer

_STD_OUTPUT_HANDLE = -11


class CompatibleHomeAdapter:
    """Fixed viewport via OS cursor home, seekable replace, or Snapshot Mode.

    Never silently scrolls. If overwrite is impossible, enters Snapshot Mode:
    at most one write to a non-seekable stream.
    """

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._force_full = True
        self._snapshot_written = False
        self._mode: str = "unknown"  # home | replace | snapshot

    @property
    def mode(self) -> str:
        return self._mode

    def prepare(self, viewport: Viewport) -> None:
        del viewport
        self._force_full = True
        self._snapshot_written = False
        self._mode = self._select_mode()

    def paint(
        self,
        frame: FrameBuffer,
        previous: FrameBuffer | None,
        viewport: Viewport,
    ) -> None:
        del previous
        mode = self._mode if self._mode != "unknown" else self._select_mode()
        self._mode = mode

        if mode == "home":
            if _windows_set_cursor_home():
                lines = _padded_lines(frame.lines, viewport)
                for line in lines:
                    self._stream.write(line + "\n")
                for _ in range(max(0, viewport.rows - len(lines))):
                    self._stream.write(" " * max(1, viewport.cols) + "\n")
                self._stream.flush()
                _windows_set_cursor_home()
                self._force_full = False
                return
            # Home unavailable at paint time — degrade without append.
            mode = "replace" if _stream_replaceable(self._stream) else "snapshot"
            self._mode = mode

        if mode == "replace":
            self._replace_stream(frame.lines, viewport)
            self._force_full = False
            return

        if self._snapshot_written:
            return
        clipped = [line[: max(1, viewport.cols)] for line in frame.lines[: max(1, viewport.rows)]]
        self._stream.write("\n".join(clipped) + "\n")
        self._stream.flush()
        self._snapshot_written = True
        self._force_full = False

    def resize(self, viewport: Viewport) -> None:
        del viewport
        self._force_full = True
        if self._mode == "snapshot":
            self._snapshot_written = False

    def shutdown(self, viewport: Viewport) -> None:
        del viewport
        if self._mode == "home" and _is_interactive(self._stream):
            self._stream.write("\n")
            self._stream.flush()

    def _select_mode(self) -> str:
        if _windows_home_available(self._stream):
            return "home"
        if _stream_replaceable(self._stream):
            return "replace"
        return "snapshot"

    def _replace_stream(self, lines: tuple[str, ...], viewport: Viewport) -> None:
        cols = max(1, viewport.cols)
        rows = max(1, viewport.rows)
        clipped = [line[:cols] for line in lines[:rows]]
        stream = self._stream
        stream.seek(0)
        stream.truncate(0)
        stream.write("\n".join(clipped) + "\n")
        stream.flush()


def _padded_lines(lines: tuple[str, ...], viewport: Viewport) -> list[str]:
    cols = max(1, viewport.cols)
    rows = max(1, viewport.rows)
    return [line[:cols].ljust(cols) for line in lines[:rows]]


def _is_interactive(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _stream_replaceable(stream: TextIO) -> bool:
    seek = getattr(stream, "seek", None)
    truncate = getattr(stream, "truncate", None)
    if not callable(seek) or not callable(truncate):
        return False
    try:
        stream.seek(0, io.SEEK_CUR)
        return True
    except (OSError, ValueError, io.UnsupportedOperation):
        return False


def _windows_home_available(stream: TextIO) -> bool:
    return os.name == "nt" and _is_interactive(stream)


def _windows_set_cursor_home() -> bool:
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
    except (AttributeError, ImportError, OSError, ValueError):
        return False
