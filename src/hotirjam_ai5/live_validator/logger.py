"""Append-only NDJSON snapshot logger for later replay analysis."""

from __future__ import annotations

import json
import time
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from hotirjam_ai5.live_validator.models import ValidatorFrame


def _jsonable(value: Any) -> Any:
    """Single-pass JSON conversion with sorted keys (matches sort_keys=True).

    Avoids ``asdict()`` then a second recursive walk.
    """
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        items = [(f.name, _jsonable(getattr(value, f.name))) for f in fields(value)]
        items.sort(key=lambda item: item[0])
        return {key: val for key, val in items}
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        items = [(str(k), _jsonable(v)) for k, v in value.items()]
        items.sort(key=lambda item: item[0])
        return {key: val for key, val in items}
    return value


class SnapshotLogger:
    """Persist every ValidatorFrame as one NDJSON line."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._count = 0
        # Keep handle open across logs (same durability via flush per write).
        self._handle: TextIO = self._path.open("a", encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    @property
    def records_written(self) -> int:
        return self._count

    def close(self) -> None:
        handle = getattr(self, "_handle", None)
        if handle is not None and not handle.closed:
            handle.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def log(self, frame: ValidatorFrame) -> None:
        _t0 = time.perf_counter()
        build_ms = 0.0
        serialize_ms = 0.0
        write_ms = 0.0
        payload: dict[str, Any] | None = None
        line: str | None = None
        try:
            _b0 = time.perf_counter()
            payload = _jsonable(frame)
            build_ms = (time.perf_counter() - _b0) * 1000.0

            _s0 = time.perf_counter()
            # Keys already sorted in _jsonable — identical to sort_keys=True.
            line = json.dumps(payload, separators=(",", ":"), sort_keys=False)
            serialize_ms = (time.perf_counter() - _s0) * 1000.0

            _w0 = time.perf_counter()
            self._handle.write(line)
            self._handle.write("\n")
            self._handle.flush()
            write_ms = (time.perf_counter() - _w0) * 1000.0
            self._count += 1
        finally:
            try:
                from hotirjam_ai5.live_validator.loop_timing import (
                    add_logging_breakdown,
                    add_logging_ms,
                    set_logging_footprint,
                )

                add_logging_ms((time.perf_counter() - _t0) * 1000.0)
                # Collect is not a distinct step (frame already in hand).
                # Flush is folded into Write (explicit flush after each line).
                add_logging_breakdown(
                    collect_ms=None,
                    build_ms=build_ms,
                    serialize_ms=serialize_ms,
                    write_ms=write_ms,
                    flush_ms=None,
                )
                # Footprint after timing so existing stage totals stay unchanged.
                if isinstance(payload, dict) and line is not None:
                    set_logging_footprint(
                        payload=payload,
                        json_size_bytes=len(line.encode("utf-8")),
                    )
            except Exception:
                pass
