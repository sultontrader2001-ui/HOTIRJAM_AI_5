"""Test / non-TTY capture adapter — replace semantics only."""

from __future__ import annotations

import io
from typing import TextIO

from hotirjam_ai5.dashboard.display.adapter import Viewport
from hotirjam_ai5.dashboard.frame_buffer import FrameBuffer


class CaptureAdapter:
    """Records painted frames in memory. Never grows a scroll log on the stream.

    Seekable streams receive replace writes (truncate + current frame).
    Non-seekable streams receive at most one Snapshot write.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream
        self._last: FrameBuffer | None = None
        self._painted: list[FrameBuffer] = []
        self._paint_count = 0
        self._snapshot_written = False

    @property
    def last_frame(self) -> FrameBuffer | None:
        return self._last

    @property
    def painted_frames(self) -> tuple[FrameBuffer, ...]:
        return tuple(self._painted)

    @property
    def paint_count(self) -> int:
        return self._paint_count

    def prepare(self, viewport: Viewport) -> None:
        del viewport
        self._snapshot_written = False

    def paint(
        self,
        frame: FrameBuffer,
        previous: FrameBuffer | None,
        viewport: Viewport,
    ) -> None:
        del previous, viewport
        self._last = frame
        self._painted.append(frame)
        self._paint_count += 1
        self._emit(frame)

    def resize(self, viewport: Viewport) -> None:
        del viewport
        self._snapshot_written = False

    def shutdown(self, viewport: Viewport) -> None:
        del viewport

    def _emit(self, frame: FrameBuffer) -> None:
        stream = self._stream
        if stream is None:
            return
        text = "\n".join(frame.lines) + "\n"
        if _stream_replaceable(stream):
            stream.seek(0)
            stream.truncate(0)
            stream.write(text)
            stream.flush()
            return
        if self._snapshot_written:
            return
        stream.write(text)
        stream.flush()
        self._snapshot_written = True


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
