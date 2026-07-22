"""Windows Bridge Sender — M1.2 runtime (network OFF).

See: bridge/docs/BRIDGE_SENDER_WINDOWS.md
See: bridge/docs/M1_2_BRIDGE_SENDER_RUNTIME.md
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hotirjam_bridge.sender.runtime import SenderRuntimeStats, TickSenderRuntime
from hotirjam_bridge.sender.tail import NdjsonTail

__all__ = [
    "NdjsonTail",
    "SenderConfig",
    "SenderOffsets",
    "SenderRuntimeStats",
    "TickSenderRuntime",
]


@dataclass(frozen=True, slots=True)
class SenderConfig:
    """Full bridge config shape (WSS fields reserved; M1.2 ignores network)."""

    tick_file: Path
    dom_file: Path | None = None
    receiver_url: str = ""
    symbol: str = "MNQ"
    mode: str = "log-only"
    poll_interval: float = 0.05
    offset_store: Path | None = None
    http_tick_url: str | None = None
    http_dom_url: str | None = None
    shared_token: str | None = None


@dataclass(frozen=True, slots=True)
class SenderOffsets:
    """Persisted tail state (byte offsets + last assigned seq)."""

    tick_byte_offset: int = 0
    dom_byte_offset: int = 0
    tick_seq: int = 0
    dom_seq: int = 0
