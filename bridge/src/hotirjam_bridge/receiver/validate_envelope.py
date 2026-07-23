"""Parse and validate Bridge envelopes (Receiver, network OFF)."""

from __future__ import annotations

import json
from typing import Any

from hotirjam_bridge.contracts import (
    BRIDGE_PROTOCOL_VERSION,
    DEFAULT_SENDER_ID,
    Channel,
    Envelope,
)


class EnvelopeValidationError(ValueError):
    """Malformed or unsupported bridge envelope."""


def parse_envelope_json(line: str) -> dict[str, Any]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise EnvelopeValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise EnvelopeValidationError("envelope must be a JSON object")
    return data


def validate_envelope_dict(data: dict[str, Any]) -> Envelope:
    """Validate envelope shape and return ``Envelope``."""
    for key in ("v", "ch", "seq", "src", "sent_at", "payload"):
        if key not in data:
            raise EnvelopeValidationError(f"missing envelope field: {key}")

    try:
        version = int(data["v"])
    except (TypeError, ValueError) as exc:
        raise EnvelopeValidationError("v must be an int") from exc
    if version != BRIDGE_PROTOCOL_VERSION:
        raise EnvelopeValidationError(
            f"unsupported protocol v={version}, expected {BRIDGE_PROTOCOL_VERSION}"
        )

    ch = data["ch"]
    if not isinstance(ch, str) or ch not in {
        Channel.TICK.value,
        Channel.DOM.value,
        Channel.HB.value,
        Channel.CTRL.value,
    }:
        raise EnvelopeValidationError(f"invalid ch: {ch!r}")

    try:
        seq = int(data["seq"])
    except (TypeError, ValueError) as exc:
        raise EnvelopeValidationError("seq must be an int") from exc
    if seq < 0:
        raise EnvelopeValidationError("seq must be >= 0")

    src = data["src"]
    if not isinstance(src, str) or not src:
        raise EnvelopeValidationError("src must be a non-empty string")

    try:
        sent_at = float(data["sent_at"])
    except (TypeError, ValueError) as exc:
        raise EnvelopeValidationError("sent_at must be a number") from exc

    payload = data["payload"]
    if not isinstance(payload, dict):
        raise EnvelopeValidationError("payload must be a JSON object")

    # Identity v2: required on new senders; missing → legacy defaults (compat).
    raw_sender = data.get("sender_id", DEFAULT_SENDER_ID)
    if raw_sender is None or not isinstance(raw_sender, str) or not raw_sender:
        sender_id = DEFAULT_SENDER_ID
    else:
        sender_id = raw_sender

    raw_session = data.get("session_id", "")
    if raw_session is None:
        session_id = ""
    elif not isinstance(raw_session, str):
        raise EnvelopeValidationError("session_id must be a string")
    else:
        session_id = raw_session

    return Envelope(
        v=version,
        ch=ch,
        seq=seq,
        src=src,
        sent_at=sent_at,
        payload=payload,
        sender_id=sender_id,
        session_id=session_id,
    )


def parse_and_validate_envelope_line(line: str) -> Envelope:
    return validate_envelope_dict(parse_envelope_json(line))
