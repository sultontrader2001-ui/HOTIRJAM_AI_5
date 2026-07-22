"""Tail an NDJSON file for newly appended lines only (live, no replay)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from hotirjam_ai5.live_data.diagnostics import IngressDiagnostics


class NdjsonFileTail:
    """Reads complete lines appended after open.

    Always starts at end-of-file so historical lines are never replayed.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        diagnostics: IngressDiagnostics | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        try:
            self.path = self.path.resolve()
        except OSError:
            # Path may not exist yet; keep expanded form.
            self.path = self.path.absolute()
        self._offset = 0
        self._initialized = False
        self._diagnostics = diagnostics or IngressDiagnostics(enabled=False)
        self._logged_missing = False
        self._diagnostics.log(f"Opened file path: {self.path}")

    @property
    def offset(self) -> int:
        return self._offset

    def mark_prefix_removed(self, *, new_size: int) -> None:
        """Caller dropped a consumed prefix and rewrote the file.

        Stay parked at EOF of the remnant so retained bytes are not re-delivered.
        """
        self._offset = max(0, int(new_size))
        self._initialized = True

    def poll(self) -> tuple[str, ...]:
        """Return newly completed NDJSON lines since the last poll."""
        if not self.path.exists():
            # Do not mark initialized: when the file appears, seek to EOF (live).
            if not self._logged_missing:
                self._diagnostics.log(f"Waiting for file (does not exist yet): {self.path}")
                self._logged_missing = True
            return ()

        try:
            size = self.path.stat().st_size
        except OSError as exc:
            self._diagnostics.log(f"stat failed: {exc}")
            return ()

        if not self._initialized:
            self._initialized = True
            self._offset = size
            self._diagnostics.log(
                f"Tail armed at EOF offset={self._offset} size={size} path={self.path}"
            )
            return ()

        if size < self._offset:
            self._diagnostics.log(
                f"File truncated/rotated (size={size} < offset={self._offset}); resetting"
            )
            self._offset = 0

        try:
            content = self._read_from_offset()
        except OSError as exc:
            self._diagnostics.log(f"read failed: {exc}")
            return ()

        last_newline = content.rfind(b"\n")
        if last_newline < 0:
            if content:
                self._diagnostics.log(
                    f"Partial line buffered ({len(content)} bytes, waiting for newline)"
                )
            return ()

        complete = content[: last_newline + 1]
        self._offset += len(complete)
        lines = tuple(
            line.decode("utf-8", errors="replace").strip()
            for line in complete.splitlines()
            if line.strip()
        )
        for line in lines:
            self._diagnostics.log(f"Line read: {line}")
        return lines

    def _read_from_offset(self) -> bytes:
        """Read file bytes from the current offset (shared-read friendly on Windows)."""
        if sys.platform == "win32":
            # Explicit shared read so NT01's append handle does not block us.
            fd = os.open(str(self.path), os.O_RDONLY | os.O_BINARY)
            try:
                os.lseek(fd, self._offset, os.SEEK_SET)
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(fd, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks)
            finally:
                os.close(fd)

        with self.path.open("rb") as stream:
            stream.seek(self._offset)
            return stream.read()
