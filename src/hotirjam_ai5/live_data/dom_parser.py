"""Parse NinjaTrader NT04 DOM NDJSON lines into DomSnapshot."""

from __future__ import annotations

import json
from typing import Any, Mapping

from hotirjam_ai5.live_data.dom import DomSnapshot

# NT04 writes source "NT03" for schema compatibility with the locked DOM contract.
ALLOWED_SOURCES = frozenset({"NT03", "NT04"})
VALID_STATUSES = frozenset({"OK", "PARTIAL", "EMPTY"})


class DomParseError(ValueError):
    """Raised when a DOM payload is invalid."""


def canonicalize_instrument(value: str) -> str:
    """Normalize instrument to root symbol (e.g. ``MNQ MAR 2025`` → ``MNQ``)."""
    text = value.strip().upper()
    if not text:
        return ""
    space = text.find(" ")
    if space > 0:
        return text[:space]
    return text


class DomParser:
    """Validates and parses one NT04 DOM JSON object."""

    def __init__(self, *, expected_symbol: str = "MNQ") -> None:
        symbol = canonicalize_instrument(expected_symbol)
        if not symbol:
            raise ValueError("expected_symbol must be non-empty")
        self._expected_symbol = symbol

    @property
    def expected_symbol(self) -> str:
        return self._expected_symbol

    def parse_line(self, line: str) -> DomSnapshot:
        text = line.strip()
        if not text:
            raise DomParseError("Empty DOM line")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DomParseError("Invalid JSON") from exc
        if not isinstance(payload, dict):
            raise DomParseError("DOM payload must be a JSON object")
        return self.parse_payload(payload)

    def parse_payload(self, payload: Mapping[str, Any]) -> DomSnapshot:
        source = payload.get("source")
        if source not in ALLOWED_SOURCES:
            raise DomParseError("Invalid source")

        instrument_raw = payload.get("instrument")
        if not isinstance(instrument_raw, str) or not instrument_raw.strip():
            raise DomParseError("Invalid instrument")
        instrument = canonicalize_instrument(instrument_raw)
        if instrument != self._expected_symbol:
            raise DomParseError(f"Unexpected instrument: {instrument}")

        timestamp_utc = payload.get("timestamp_utc")
        if not isinstance(timestamp_utc, str) or not timestamp_utc.strip():
            raise DomParseError("Invalid timestamp_utc")

        depth_levels = payload.get("depth_levels")
        if not isinstance(depth_levels, int) or isinstance(depth_levels, bool) or depth_levels < 0:
            raise DomParseError("Invalid depth_levels")

        total_bid = self._require_non_negative_int(payload.get("bid_total_size"), "bid_total_size")
        total_ask = self._require_non_negative_int(payload.get("ask_total_size"), "ask_total_size")

        bids = payload.get("bids")
        asks = payload.get("asks")
        if not isinstance(bids, list) or not isinstance(asks, list):
            raise DomParseError("bids and asks must be arrays")

        best_bid_size = self._best_level_size(bids, "bids")
        best_ask_size = self._best_level_size(asks, "asks")

        status = payload.get("status", "OK")
        if status not in VALID_STATUSES:
            raise DomParseError("Invalid status")

        return DomSnapshot(
            timestamp_utc=timestamp_utc.strip(),
            instrument=instrument,
            depth_levels=depth_levels,
            best_bid_size=best_bid_size,
            best_ask_size=best_ask_size,
            total_bid_size=total_bid,
            total_ask_size=total_ask,
            status=str(status),
        )

    @staticmethod
    def _require_non_negative_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise DomParseError(f"Invalid {field_name}")
        if value < 0:
            raise DomParseError(f"Invalid {field_name}")
        return value

    @staticmethod
    def _best_level_size(levels: list[Any], side_name: str) -> int | None:
        if not levels:
            return None
        level = levels[0]
        if not isinstance(level, Mapping):
            raise DomParseError(f"{side_name} entries must be objects")
        size = level.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise DomParseError(f"Invalid {side_name} size")
        return size
