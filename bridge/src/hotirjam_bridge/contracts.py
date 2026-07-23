"""Shared wire contracts for Bridge Sender (Windows) and Receiver (Mac).

Design-phase constants and envelope shape only.
No network I/O. No AI imports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


BRIDGE_PROTOCOL_VERSION = 1

# Envelope Identity v2 — stable sender label (ops may override via CLI)
DEFAULT_SENDER_ID = "HOTIRJAM_WINDOWS_01"

# Suggested defaults (ops may override)
DEFAULT_WSS_PORT = 9443
DEFAULT_WSS_PATH = "/bridge"
DEFAULT_HTTP_TICK_PORT = 8765
DEFAULT_HTTP_DOM_PORT = 8766
DEFAULT_SYMBOL = "MNQ"

TICK_FILENAME = "mnq_ticks.ndjson"
DOM_FILENAME = "mnq_dom.ndjson"


class Channel(StrEnum):
    TICK = "tick"
    DOM = "dom"
    HB = "hb"
    CTRL = "ctrl"


class ControlType(StrEnum):
    HELLO = "hello"
    HELLO_ACK = "hello_ack"
    GOODBYE = "goodbye"
    GAP = "gap"


class SourceTag(StrEnum):
    NT01 = "NT01"
    NT03 = "NT03"
    BRIDGE_SENDER = "BRIDGE_SENDER"
    BRIDGE_RECEIVER = "BRIDGE_RECEIVER"


@dataclass(frozen=True, slots=True)
class Envelope:
    """One bridge transport message (HTTP POST body / logical frame).

    ``payload`` for tick/dom MUST be the exact NT01/NT03 object.
    Envelope metadata must not be merged into journal lines on Mac.

    Identity v2: dedupe key is ``(session_id, ch, seq)``.
    ``sender_id`` is stable; ``session_id`` is UUID4 per sender process start.
    """

    v: int
    ch: str
    seq: int
    src: str
    sent_at: float
    payload: dict[str, Any]
    sender_id: str = DEFAULT_SENDER_ID
    session_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Envelope:
        return cls(
            v=int(data["v"]),
            ch=str(data["ch"]),
            seq=int(data["seq"]),
            src=str(data["src"]),
            sent_at=float(data["sent_at"]),
            payload=dict(data["payload"]),
            sender_id=str(data.get("sender_id") or DEFAULT_SENDER_ID),
            session_id=str(data.get("session_id") or ""),
        )


# NT01 payload keys (frozen contract — mirror docs/NT01; do not extend here lightly)
NT01_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "timestamp",
        "symbol",
        "last_price",
        "bid",
        "ask",
        "volume",
    }
)

# NT03 core keys (subset used for bridge accept gate; full schema in NT03 docs)
NT03_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "timestamp_utc",
        "instrument",
        "bids",
        "asks",
        "status",
    }
)
