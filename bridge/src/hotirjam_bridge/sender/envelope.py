"""Build Bridge envelopes for Sender (no network)."""

from __future__ import annotations

import time
from typing import Any, Callable

from hotirjam_bridge.contracts import (
    BRIDGE_PROTOCOL_VERSION,
    Channel,
    Envelope,
    SourceTag,
)


def wrap_tick(
    payload: dict[str, Any],
    *,
    seq: int,
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
    )
