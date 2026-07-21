"""Append-only NDJSON snapshot logger for later replay analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from hotirjam_ai5.live_validator.models import ValidatorFrame


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


class SnapshotLogger:
    """Persist every ValidatorFrame as one NDJSON line."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._count = 0

    @property
    def path(self) -> Path:
        return self._path

    @property
    def records_written(self) -> int:
        return self._count

    def log(self, frame: ValidatorFrame) -> None:
        payload = _jsonable(frame)
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
        self._count += 1
