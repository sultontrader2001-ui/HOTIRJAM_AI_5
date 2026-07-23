"""Build Bridge envelopes for Sender (no network)."""

from __future__ import annotations

import time
from typing import Any, Callable

from hotirjam_bridge.contracts import (
    BRIDGE_PROTOCOL_VERSION,
    DEFAULT_SENDER_ID,
    Channel,
    Envelope,
    SourceTag,
)


def wrap_tick(
    payload: dict[str, Any],
    *,
    seq: int,
    session_id: str,
    sender_id: str = DEFAULT_SENDER_ID,
    sent_at: float | None = None,
    clock: Callable[[], float] | None = None,
) -> Envelope:
    """Wrap a validated NT01 payload in a tick channel envelope."""
    now = sent_at if sent_at is not None else (clock or time.time)()
    return Envelope(
        v=BRIDGE_PROTOCOL_VERSION,
        ch=Channel.TICK.value,
        seq=int(seq),
        src=SourceTag.NT01.value,
        sent_at=float(now),
        payload=payload,
        sender_id=str(sender_id),
        session_id=str(session_id),
    )


def wrap_dom(
    payload: dict[str, Any],
    *,
    seq: int,
    session_id: str,
    sender_id: str = DEFAULT_SENDER_ID,
    sent_at: float | None = None,
    clock: Callable[[], float] | None = None,
) -> Envelope:
    """Wrap a validated NT03 payload in a dom channel envelope."""
    now = sent_at if sent_at is not None else (clock or time.time)()
    return Envelope(
        v=BRIDGE_PROTOCOL_VERSION,
        ch=Channel.DOM.value,
        seq=int(seq),
        src=SourceTag.NT03.value,
        sent_at=float(now),
        payload=payload,
        sender_id=str(sender_id),
        session_id=str(session_id),
    )
