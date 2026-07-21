"""JSONL writer for completed Performance Tracker evaluations."""

from __future__ import annotations

import json
from pathlib import Path

from hotirjam_ai5.performance.models import SignalRecord

DEFAULT_PERFORMANCE_LOG_PATH = Path("logs") / "performance_log.jsonl"


class PerformanceLogWriter:
    """Appends one JSON object per completed signal evaluation."""

    def __init__(self, path: Path | str = DEFAULT_PERFORMANCE_LOG_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def write_completed(self, record: SignalRecord) -> None:
        """Append one completed evaluation. Pending records are rejected."""
        if record.evaluation_time is None or record.exit_price is None:
            raise ValueError("completed signal requires exit_price and evaluation_time")
        if record.points is None:
            raise ValueError("completed signal requires points")
        payload = {
            "signal_id": record.signal_id,
            "symbol": record.symbol,
            "decision": record.decision,
            "result": record.result.value,
            "entry_price": record.entry_price,
            "exit_price": record.exit_price,
            "points": record.points,
            "buy_score": record.buy_score,
            "sell_score": record.sell_score,
            "buy_confidence": record.buy_confidence,
            "sell_confidence": record.sell_confidence,
            "market_state": record.market_state,
            "behavior": record.behavior,
            "physics": {
                "velocity": record.physics.velocity,
                "acceleration": record.physics.acceleration,
            },
            "liquidity": {
                "shift": record.liquidity.shift,
                "imbalance": record.liquidity.imbalance,
            },
            "entry_time": {
                "utc": record.entry_time.utc,
                "new_york": record.entry_time.new_york,
                "tashkent": record.entry_time.tashkent,
            },
            "evaluation_time": {
                "utc": record.evaluation_time.utc,
                "new_york": record.evaluation_time.new_york,
                "tashkent": record.evaluation_time.tashkent,
            },
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
