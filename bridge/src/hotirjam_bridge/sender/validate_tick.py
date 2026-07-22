"""NT01 tick payload validation for Bridge Sender.

Contract mirror of docs/NT01 — local to bridge package (no AI imports).
"""

from __future__ import annotations

import json
import math
from typing import Any

from hotirjam_bridge.contracts import NT01_REQUIRED_KEYS


class TickValidationError(ValueError):
    """Raised when a tick line fails NT01 contract checks."""


def parse_tick_json(line: str) -> dict[str, Any]:
    """Parse one NDJSON line into a dict."""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise TickValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TickValidationError("tick payload must be a JSON object")
    return payload


def validate_nt01_tick(
    payload: dict[str, Any],
    *,
    expected_symbol: str = "MNQ",
) -> dict[str, Any]:
    """Validate NT01 required fields and basic numeric rules.

    Returns the same payload dict on success (unchanged).
    """
    missing = NT01_REQUIRED_KEYS - payload.keys()
    if missing:
        raise TickValidationError(f"missing keys: {sorted(missing)}")

    symbol = payload.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise TickValidationError("symbol must be a non-empty string")
    if expected_symbol and symbol != expected_symbol:
        raise TickValidationError(
            f"symbol mismatch: got {symbol!r}, expected {expected_symbol!r}"
        )

    for key in ("timestamp", "last_price", "bid", "ask", "volume"):
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TickValidationError(f"{key} must be a number")
        number = float(value)
        if not math.isfinite(number):
            raise TickValidationError(f"{key} must be finite")

    last_price = float(payload["last_price"])
    bid = float(payload["bid"])
    ask = float(payload["ask"])
    volume = float(payload["volume"])
    if last_price <= 0.0:
        raise TickValidationError("last_price must be > 0")
    if bid <= 0.0:
        raise TickValidationError("bid must be > 0")
    if ask <= 0.0:
        raise TickValidationError("ask must be > 0")
    if ask < bid:
        raise TickValidationError("ask must be >= bid")
    if volume < 0.0:
        raise TickValidationError("volume must be >= 0")

    return payload
