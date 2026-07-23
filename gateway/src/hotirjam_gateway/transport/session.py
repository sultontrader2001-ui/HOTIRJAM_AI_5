"""Transport session metrics for one accepted client connection."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class TransportSession:
    """Tracks one active transport connection (no trading semantics)."""

    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    connected_at: float = field(default_factory=time.time)
    last_message_time: float | None = None
    bytes_received: int = 0
    messages_received: int = 0
    remote_addr: str = ""

    def record_bytes(self, nbytes: int, *, when: float | None = None) -> None:
        """Accumulate raw bytes read from the socket."""
        if nbytes < 0:
            raise ValueError("nbytes must be >= 0")
        self.bytes_received += nbytes
        if when is not None:
            self.last_message_time = when

    def record_message(self, nbytes: int, *, when: float | None = None) -> None:
        """Record one complete UTF-8 JSON message (valid or invalid)."""
        now = time.time() if when is None else when
        self.record_bytes(nbytes, when=now)
        self.messages_received += 1
        self.last_message_time = now
