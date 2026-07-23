"""Raw message receiver — UTF-8 JSON lines only; no trading-field parsing."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from hotirjam_gateway.logging import get_logger
from hotirjam_gateway.transport.session import TransportSession

_log = get_logger(__name__)

# Validation layer receives raw text + parsed JSON object.
# Sprint 2.1 does not interpret Tick/DOM/AI fields.
ValidationHandler = Callable[[str, Any, TransportSession], None]


class ValidationLayer(Protocol):
    """Sink for successfully decoded JSON messages (structure only)."""

    def on_raw_message(
        self,
        raw: str,
        data: object,
        session: TransportSession,
    ) -> None: ...


class PassThroughValidation:
    """Default validation stub: accept any JSON value; record nothing."""

    def on_raw_message(
        self,
        raw: str,
        data: object,
        session: TransportSession,
    ) -> None:
        return None


class MessageReceiver:
    """Buffer socket bytes, split NDJSON lines, decode UTF-8 JSON.

    Valid JSON is forwarded to the validation layer unchanged.
    Invalid JSON is logged and not forwarded.
    """

    def __init__(
        self,
        session: TransportSession,
        validation: ValidationLayer | None = None,
        *,
        on_invalid: Callable[[str, TransportSession], None] | None = None,
    ) -> None:
        self._session = session
        self._validation: ValidationLayer = validation or PassThroughValidation()
        self._on_invalid = on_invalid
        self._buffer = bytearray()

    @property
    def session(self) -> TransportSession:
        return self._session

    def feed(self, chunk: bytes) -> int:
        """Append ``chunk`` and process complete lines. Returns messages handled."""
        if not chunk:
            return 0
        self._buffer.extend(chunk)
        handled = 0
        while True:
            nl = self._buffer.find(b"\n")
            if nl < 0:
                break
            line = bytes(self._buffer[:nl])
            del self._buffer[: nl + 1]
            # Allow CRLF
            if line.endswith(b"\r"):
                line = line[:-1]
            if not line.strip():
                continue
            self._handle_line(line)
            handled += 1
        return handled

    def flush_incomplete(self) -> None:
        """Drop any trailing incomplete line without treating it as a message."""
        self._buffer.clear()

    def _handle_line(self, line: bytes) -> None:
        raw: str
        try:
            raw = line.decode("utf-8")
        except UnicodeDecodeError:
            self._session.record_message(len(line))
            _log.warning(
                "Invalid Message",
                extra={
                    "gateway_event": "Invalid Message",
                    "connection_id": self._session.connection_id,
                    "reason": "utf8_decode",
                },
            )
            if self._on_invalid is not None:
                self._on_invalid("<binary>", self._session)
            return

        self._session.record_message(len(line))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            _log.warning(
                "Invalid Message",
                extra={
                    "gateway_event": "Invalid Message",
                    "connection_id": self._session.connection_id,
                    "reason": "json_decode",
                },
            )
            if self._on_invalid is not None:
                self._on_invalid(raw, self._session)
            return

        _log.info(
            "Message Received",
            extra={
                "gateway_event": "Message Received",
                "connection_id": self._session.connection_id,
                "messages_received": self._session.messages_received,
                "bytes_received": self._session.bytes_received,
            },
        )
        self._validation.on_raw_message(raw, data, self._session)
