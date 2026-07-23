"""Read-only NDJSON byte-offset tail (Windows Sender).

No network. No AI imports. Does not modify the source file.

Always uses binary I/O. On Windows, text-mode ``seek``/``tell`` must not be
mixed with ``stat().st_size`` — that parks the tick cursor past EOF after
startup-at-EOF while DOM (often started empty) keeps flowing.
"""

from __future__ import annotations

from pathlib import Path


class NdjsonTail:
    """Tail complete NDJSON lines from a growing file (byte offsets)."""

    def __init__(self, path: Path, *, start_at_eof: bool = True) -> None:
        self.path = Path(path)
        self._offset = 0
        self._file_id: tuple[int, int] | None = None
        if start_at_eof and self.path.is_file():
            try:
                st = self.path.stat()
            except OSError:
                return
            self._offset = int(st.st_size)
            self._file_id = (int(st.st_dev), int(st.st_ino))

    @property
    def offset(self) -> int:
        return self._offset

    def seek(self, offset: int) -> None:
        self._offset = max(0, int(offset))

    def poll(self) -> list[str]:
        """Return newly completed non-empty lines; leave incomplete line unread."""
        if not self.path.is_file():
            self._file_id = None
            return []

        try:
            st = self.path.stat()
        except OSError:
            return []

        size = int(st.st_size)
        file_id = (int(st.st_dev), int(st.st_ino))

        # Same path, new inode/device (replace) — re-arm at EOF of the new file.
        # On Windows st_ino may be 0; still safe when size shrinks (handled below).
        if self._file_id is not None and file_id != self._file_id and file_id != (0, 0):
            self._offset = size
            self._file_id = file_id
            return []
        self._file_id = file_id

        # Journal truncated/replaced (common after first session write on Windows).
        # Without this, seek stays past EOF and continuous tick forwarding stops forever
        # while DOM (separate file) keeps flowing.
        if size < self._offset:
            self._offset = size

        if size <= self._offset:
            return []

        lines: list[str] = []
        with self.path.open("rb") as handle:
            handle.seek(self._offset)
            while True:
                line_start = handle.tell()
                raw = handle.readline()
                if not raw:
                    break
                if not raw.endswith(b"\n"):
                    # Partial last line — wait for writer to finish.
                    handle.seek(line_start)
                    break
                self._offset = handle.tell()
                text = raw.decode("utf-8", errors="replace").strip()
                # Strip UTF-8 BOM if present on first line after recreate.
                if text.startswith("\ufeff"):
                    text = text.lstrip("\ufeff")
                if text:
                    lines.append(text)
        return lines
