"""Parse NinjaTrader NT01 NDJSON tick lines into LiveTick."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from hotirjam_ai5.live_data.tick import LiveTick

REQUIRED_FIELDS = (
    "timestamp",
    "symbol",
    "last_price",
    "bid",
    "ask",
    "volume",
)


class TickParseError(ValueError):
    """Raised when a tick payload is invalid."""


class TickParser:
    """Validates and parses one NT01 tick JSON object."""

    def __init__(self, *, expected_symbol: str = "MNQ") -> None:
        symbol = expected_symbol.strip().upper()
        if not symbol:
            raise ValueError("expected_symbol must be non-empty")
        self._expected_symbol = symbol

    @property
    def expected_symbol(self) -> str:
        return self._expected_symbol

    def parse_line(self, line: str) -> LiveTick:
        """Parse one NDJSON line into a LiveTick."""
        text = line.strip()
        if not text:
            raise TickParseError("Empty tick line")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TickParseError("Invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TickParseError("Tick payload must be a JSON object")
        return self.parse_payload(payload)

    def parse_payload(self, payload: Mapping[str, Any]) -> LiveTick:
        """Parse one mapping into a LiveTick."""
        missing = [name for name in REQUIRED_FIELDS if name not in payload]
        if missing:
            raise TickParseError(f"Missing fields: {', '.join(missing)}")

        symbol = payload["symbol"]
        if not isinstance(symbol, str) or not symbol.strip():
            raise TickParseError("Invalid symbol")
        symbol = symbol.strip().upper()
        if symbol != self._expected_symbol:
            raise TickParseError(f"Unexpected symbol: {symbol}")

        timestamp = self._require_finite_number(payload["timestamp"], "timestamp")
        last_price = self._require_positive_price(payload["last_price"], "last_price")
        bid = self._require_positive_price(payload["bid"], "bid")
        ask = self._require_positive_price(payload["ask"], "ask")
        volume = self._require_finite_number(payload["volume"], "volume")
        if volume < 0:
            raise TickParseError("Invalid volume")
        if ask < bid:
            raise TickParseError("Invalid spread")

        return LiveTick(
            timestamp=timestamp,
            symbol=symbol,
            last_price=last_price,
            bid=bid,
            ask=ask,
            volume=volume,
        )

    @staticmethod
    def _require_finite_number(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TickParseError(f"Invalid {field_name}")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TickParseError(f"Invalid {field_name}") from exc
        if not math.isfinite(number):
            raise TickParseError(f"Invalid {field_name}")
        return number

    @classmethod
    def _require_positive_price(cls, value: Any, field_name: str) -> float:
        number = cls._require_finite_number(value, field_name)
        if number <= 0:
            raise TickParseError(f"Invalid {field_name}")
        return number
