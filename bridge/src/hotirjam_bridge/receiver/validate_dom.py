"""NT03 DOM payload validation for Bridge Receiver (local contract copy)."""

from __future__ import annotations

from typing import Any

from hotirjam_bridge.contracts import NT03_REQUIRED_KEYS


class DomValidationError(ValueError):
    """Raised when a DOM payload fails NT03 accept-gate checks."""


def validate_nt03_dom(
    payload: dict[str, Any],
    *,
    expected_symbol: str = "MNQ",
) -> dict[str, Any]:
    missing = NT03_REQUIRED_KEYS - payload.keys()
    if missing:
        raise DomValidationError(f"missing keys: {sorted(missing)}")

    instrument = payload.get("instrument")
    if not isinstance(instrument, str) or not instrument:
        raise DomValidationError("instrument must be a non-empty string")
    if expected_symbol and instrument != expected_symbol:
        raise DomValidationError(
            f"instrument mismatch: got {instrument!r}, expected {expected_symbol!r}"
        )

    if not isinstance(payload.get("bids"), list):
        raise DomValidationError("bids must be a list")
    if not isinstance(payload.get("asks"), list):
        raise DomValidationError("asks must be a list")
    if not isinstance(payload.get("timestamp_utc"), str):
        raise DomValidationError("timestamp_utc must be a string")
    if not isinstance(payload.get("status"), str):
        raise DomValidationError("status must be a string")
    return payload
