"""JSONL writer for completed entry-timing audits."""

from __future__ import annotations

import json
from pathlib import Path

from hotirjam_ai5.entry_timing.models import TimingRecord

DEFAULT_TIMING_LOG_PATH = Path("logs") / "entry_timing_log.jsonl"


class TimingLogWriter:
    """Appends one JSON object per completed timing audit."""

    def __init__(self, path: Path | str = DEFAULT_TIMING_LOG_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def write_completed(self, record: TimingRecord) -> None:
        if record.timing_class.value == "PENDING":
            raise ValueError("cannot log a PENDING timing record")
        if record.mfe is None or record.mae is None:
            raise ValueError("completed timing record requires MFE and MAE")
        payload = {
            "signal_id": record.signal_id,
            "symbol": record.symbol,
            "decision": record.decision,
            "entry_price": record.entry_price,
            "entry_time": record.entry_time,
            "exit_price": record.exit_price,
            "exit_time": record.exit_time,
            "mfe": record.mfe,
            "mae": record.mae,
            "timing_class": record.timing_class.value,
            "classification_reason": record.classification_reason,
            "checkpoints": [
                {
                    "offset_seconds": c.offset_seconds,
                    "price": c.price,
                    "points": c.points,
                }
                for c in record.checkpoints
            ],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
