"""Safe NDJSON size retention — only after proven consumption.

Rules (AI-safety):
- Never delete bytes that have not been consumed by the live tailer.
- If consumed_offset is unknown/zero, do nothing.
- Snapshot log rotation only moves already-persisted frames.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from hotirjam_ai5.retention.stats import record_retention_event


def rotate_log_if_needed(path: Path, *, max_bytes: int) -> bool:
    """Rotate append log when over ``max_bytes``.

    Keeps ``path`` (fresh current) and ``path.previous`` only.
    Caller must close any open handle before calling.
    Returns True if rotated.
    """
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size <= max_bytes:
            return False
    except OSError:
        return False

    previous = path.with_name(path.name + ".previous")
    older = path.with_name(path.name + ".previous.older")
    try:
        if older.exists():
            older.unlink()
        if previous.exists():
            previous.unlink()
        os.replace(path, previous)
        path.touch()
        record_retention_event()
        return True
    except OSError:
        return False


def enforce_ndjson_size_limit(
    path: Path,
    *,
    max_bytes: int,
    consumed_offset: int | None,
) -> bool:
    """Drop only the proven-consumed prefix when the file exceeds ``max_bytes``.

    ``consumed_offset`` must be the byte offset through which the live ingress
    has already returned complete lines. Bytes at/after that offset are still
    live / unprocessed and are never removed.

    If ``consumed_offset`` is None or <= 0, this is a no-op (uncertainty).
    """
    path = Path(path)
    if consumed_offset is None or consumed_offset <= 0:
        return False

    try:
        size = path.stat().st_size if path.is_file() else 0
    except OSError:
        return False
    if size <= max_bytes:
        return False

    # Can only remove [0, consumed_offset). Keep [consumed_offset, size).
    drop_through = min(consumed_offset, size)
    if drop_through <= 0:
        return False

    try:
        with path.open("rb") as handle:
            handle.seek(drop_through)
            retained = handle.read()
    except OSError:
        return False

    # Align to next newline so the first retained line is complete.
    # (drop_through is already at a line boundary from NdjsonFileTail.)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(retained)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        record_retention_event()
        return True
    except OSError:
        if os.path.exists(temporary_name):
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        return False
