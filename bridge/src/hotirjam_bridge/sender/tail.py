"""Read-only NDJSON byte-offset tail (Windows Sender).

No network. No AI imports. Does not modify the source file.
"""

from __future__ import annotations

from pathlib import Path


class NdjsonTail:
    """Tail complete NDJSON lines from a growing file."""

    def __init__(self, path: Path, *, start_at_eof: bool = True) -> None:
        self.path = Path(path)
        self._offset = 0
        if start_at_eof and self.path.is_file():
            self._offset = self.path.stat().st_size

    @property
    def offset(self) -> int:
        return self._offset

    def seek(self, offset: int) -> None:
        self._offset = max(0, int(offset))

    def poll(self) -> list[str]:
        """Return newly completed non-empty lines; leave incomplete line unread."""
        if not self.path.is_file():
            return []

        try:
            size = self.path.stat().st_size
        except OSError:
            return []

        # Journal truncated/replaced (common after first session write on Windows).
        # Without this, seek stays past EOF and continuous tick forwarding stops forever
        # while DOM (separate file) keeps flowing.
        if size < self._offset:
            self._offset = size

        lines: list[str] = []
        with self.path.open("r", encoding="utf-8") as handle:
            handle.seek(self._offset)
            while True:
                line_start = handle.tell()
                raw = handle.readline()
                if not raw:
                    break
                if not raw.endswith("\n"):
                    # Partial last line — wait for writer to finish.
                    handle.seek(line_start)
                    break
                self._offset = handle.tell()
                text = raw.strip()
                if text:
                    lines.append(text)
        return lines
