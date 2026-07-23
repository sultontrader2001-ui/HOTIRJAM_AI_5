"""Append-only NDJSON journal writer with integrity verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hotirjam_bridge.receiver.integrity import (
    assert_payload_line_matches,
    canonical_payload_line,
)


class NdjsonJournalWriter:
    """Write payload-only NDJSON lines; verify bytes after each write."""

    def __init__(self, path: Path, *, flush_each_line: bool = True) -> None:
        self.path = Path(path)
        self.flush_each_line = flush_each_line
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
        self.lines_written = 0

    def append_payload(self, payload: dict[str, Any]) -> str:
        """Append canonical payload line; return SHA-256 of written bytes."""
        line = canonical_payload_line(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            if self.flush_each_line:
                handle.flush()

        last = _read_last_line(self.path)
        digest = assert_payload_line_matches(payload, last)
        self.lines_written += 1
        return digest


def _read_last_line(path: Path) -> str:
    """Read only the trailing NDJSON line (avoid O(n) full-file scans)."""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        if size == 0:
            raise ValueError(f"journal empty after write: {path}")
        # Walk backward to the previous newline (or start of file).
        pos = size - 1
        # Skip final newline byte(s)
        while pos >= 0:
            handle.seek(pos)
            ch = handle.read(1)
            if ch not in (b"\n", b"\r"):
                break
            pos -= 1
        end = pos + 1
        while pos >= 0:
            handle.seek(pos)
            if handle.read(1) == b"\n":
                pos += 1
                break
            pos -= 1
        else:
            pos = 0
        handle.seek(pos)
        data = handle.read(end - pos + 1)
    line = data.decode("utf-8")
    if not line.endswith("\n"):
        line = line + "\n"
    return line
