"""Wire envelope contract (Identity v2 shape). Gateway-only — no AI imports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


GATEWAY_PROTOCOL_VERSION = 1
DEFAULT_SENDER_ID = "HOTIRJAM_WINDOWS_01"


class Channel(StrEnum):
    TICK = "tick"
    DOM = "dom"
    HB = "hb"
    CTRL = "ctrl"


@dataclass(frozen=True, slots=True)
class Envelope:
    """One Gateway transport message.

    Identity v2 dedupe key (receiver side): ``(session_id, ch, seq)``.
    ``payload`` for tick/dom must remain venue Market Truth shape; Gateway
    metadata must not be merged into journal lines.
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

    def dedupe_key(self) -> tuple[str, str, int]:
        """Receiver-side identity: session, channel, sequence."""
        return (self.session_id, self.ch, int(self.seq))
