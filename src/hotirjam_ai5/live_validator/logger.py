"""Append-only NDJSON snapshot logger for later replay analysis."""

from __future__ import annotations

import json
import time
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from hotirjam_ai5.live_validator.diagnostic_projection import DiagnosticLogProjection
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

    def __init__(
        self,
        path: str | Path,
        *,
        max_file_size_bytes: int | None = None,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._count = 0
        if max_file_size_bytes is None:
            try:
                from hotirjam_ai5.retention import load_retention_config

                max_file_size_bytes = load_retention_config().snapshot_log_max_bytes
            except Exception:
                max_file_size_bytes = 100 * 1024 * 1024
        self._max_file_size_bytes = int(max_file_size_bytes)
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

    def _maybe_rotate(self) -> tuple[float, float]:
        """Rotate after persistence when over size; reopen for continued appends.

        Returns exclusive ``(rotate_ms, reopen_ms)``. Timers never overlap.
        """
        rotate_ms = 0.0
        reopen_ms = 0.0
        _r0 = time.perf_counter()
        try:
            try:
                over = (
                    self._path.is_file()
                    and self._path.stat().st_size > self._max_file_size_bytes
                )
            except OSError:
                rotate_ms = (time.perf_counter() - _r0) * 1000.0
                return rotate_ms, reopen_ms
            if not over:
                rotate_ms = (time.perf_counter() - _r0) * 1000.0
                return rotate_ms, reopen_ms
            if not self._handle.closed:
                self._handle.close()
            from hotirjam_ai5.retention import rotate_log_if_needed

            rotate_log_if_needed(self._path, max_bytes=self._max_file_size_bytes)
            rotate_ms = (time.perf_counter() - _r0) * 1000.0

            _o0 = time.perf_counter()
            self._handle = self._path.open("a", encoding="utf-8")
            reopen_ms = (time.perf_counter() - _o0) * 1000.0
        except Exception:
            rotate_ms = max(rotate_ms, (time.perf_counter() - _r0) * 1000.0 - reopen_ms)
            try:
                if getattr(self, "_handle", None) is None or self._handle.closed:
                    _o0 = time.perf_counter()
                    self._handle = self._path.open("a", encoding="utf-8")
                    reopen_ms += (time.perf_counter() - _o0) * 1000.0
            except Exception:
                pass
        return rotate_ms, reopen_ms

    def log(self, frame: ValidatorFrame) -> None:
        _t0 = time.perf_counter()
        frame_prep_ms = 0.0
        diagnostics_attachment_ms = 0.0
        serialize_ms = 0.0
        write_ms = 0.0
        flush_ms = 0.0
        rotate_ms = 0.0
        reopen_ms = 0.0
        payload: dict[str, Any] | None = None
        line: str | None = None
        try:
            # H-6.9.4: never serialize runtime report R (objective_diagnostics).
            # Diagnostics section is projection P envelope only.
            items: list[tuple[str, Any]] = []
            for f in fields(frame):
                name = f.name
                if name == "objective_diagnostics":
                    continue
                value = getattr(frame, name)
                _p0 = time.perf_counter()
                if name == "diagnostic_log":
                    if isinstance(value, DiagnosticLogProjection):
                        envelope = value.as_log_envelope()
                        # Flatten envelope into top-level frame keys per schema.
                        for key, val in envelope.items():
                            items.append((key, val))
                        diagnostics_attachment_ms += (
                            time.perf_counter() - _p0
                        ) * 1000.0
                        continue
                    converted = None
                    diagnostics_attachment_ms += (time.perf_counter() - _p0) * 1000.0
                    # Omit null diagnostic_log key entirely when absent.
                    continue
                converted = _jsonable(value)
                frame_prep_ms += (time.perf_counter() - _p0) * 1000.0
                items.append((name, converted))
            items.sort(key=lambda item: item[0])
            payload = {key: val for key, val in items}

            _s0 = time.perf_counter()
            line = json.dumps(payload, separators=(",", ":"), sort_keys=False)
            serialize_ms = (time.perf_counter() - _s0) * 1000.0

            _w0 = time.perf_counter()
            self._handle.write(line)
            self._handle.write("\n")
            write_ms = (time.perf_counter() - _w0) * 1000.0

            _f0 = time.perf_counter()
            self._handle.flush()
            flush_ms = (time.perf_counter() - _f0) * 1000.0

            self._count += 1
            rotate_ms, reopen_ms = self._maybe_rotate()
        finally:
            try:
                from hotirjam_ai5.live_validator.loop_timing import (
                    add_logging_breakdown,
                    add_logging_exclusive,
                    add_logging_ms,
                    set_logging_footprint,
                )
                from hotirjam_ai5.live_validator.snapshot_logger_probe import (
                    record_snapshot_logger_phases,
                )

                total_ms = (time.perf_counter() - _t0) * 1000.0
                add_logging_ms(total_ms)
                add_logging_breakdown(
                    collect_ms=None,
                    build_ms=frame_prep_ms + diagnostics_attachment_ms,
                    serialize_ms=serialize_ms,
                    write_ms=write_ms + flush_ms,
                    flush_ms=None,
                )
                add_logging_exclusive(
                    build_ms=frame_prep_ms + diagnostics_attachment_ms,
                    serialize_ms=serialize_ms,
                    write_ms=write_ms,
                    flush_ms=flush_ms,
                    rotate_ms=rotate_ms,
                    reopen_ms=reopen_ms,
                )
                record_snapshot_logger_phases(
                    frame_prep_ms=frame_prep_ms,
                    diagnostics_attachment_ms=diagnostics_attachment_ms,
                    serialize_ms=serialize_ms,
                    write_ms=write_ms,
                    flush_ms=flush_ms,
                    rotation_check_ms=rotate_ms,
                    reopen_ms=reopen_ms,
                    total_ms=total_ms,
                )
                if isinstance(payload, dict) and line is not None:
                    set_logging_footprint(
                        payload=payload,
                        json_size_bytes=len(line.encode("utf-8")),
                    )
            except Exception:
                pass
