"""Tail an NDJSON file for newly appended lines only (live, no replay)."""

from __future__ import annotations

from pathlib import Path


class NdjsonFileTail:
    """Reads complete lines appended after open.

    Always starts at end-of-file so historical lines are never replayed.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._offset = 0
        self._initialized = False

    @property
    def offset(self) -> int:
        return self._offset

    def poll(self) -> tuple[str, ...]:
        """Return newly completed NDJSON lines since the last poll."""
        if not self.path.exists():
            self._initialized = True
            return ()

        size = self.path.stat().st_size
        if not self._initialized:
            self._initialized = True
            self._offset = size
            return ()

        if size < self._offset:
            # File truncated/rotated — resume from start of new content.
            self._offset = 0

        with self.path.open("rb") as stream:
            stream.seek(self._offset)
            content = stream.read()

        last_newline = content.rfind(b"\n")
        if last_newline < 0:
            return ()

        complete = content[: last_newline + 1]
        self._offset += len(complete)
        return tuple(
            line.decode("utf-8").strip()
            for line in complete.splitlines()
            if line.strip()
        )
