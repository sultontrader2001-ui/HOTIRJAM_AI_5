"""Mac Bridge Receiver — runtime (network OFF).

See: bridge/docs/BRIDGE_RECEIVER_MAC.md
See: bridge/docs/M1_3_BRIDGE_RECEIVER_RUNTIME.md
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hotirjam_bridge.receiver.runtime import (
    EnvelopeReceiverRuntime,
    ReceiverRuntimeStats,
)

__all__ = [
    "EnvelopeReceiverRuntime",
    "ReceiverConfig",
    "ReceiverHealth",
    "ReceiverRuntimeStats",
]


@dataclass(frozen=True, slots=True)
class ReceiverConfig:
    """Configuration shape for Mac Receiver CLI / future WSS."""

    out_dir: Path
    bind_host: str = "0.0.0.0"
    wss_port: int = 9443
    http_port: int = 8765
    expected_symbol: str = "MNQ"
    shared_token: str | None = None
    flush_each_line: bool = True
    dedupe_window: int = 10_000


@dataclass(frozen=True, slots=True)
class ReceiverHealth:
    """Health snapshot for GET /health (future)."""

    ok: bool
    bridge_connected: bool
    ticks_accepted: int
    dom_accepted: int
    last_tick_at: float | None
    last_dom_at: float | None
    last_hb_at: float | None
