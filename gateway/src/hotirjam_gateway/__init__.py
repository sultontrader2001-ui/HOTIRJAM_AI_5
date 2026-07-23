"""HOTIRJAM Gateway — transport skeleton (Sprint 1).

No AI imports. No NinjaTrader libraries. No broker APIs. No trading logic.
"""

from __future__ import annotations

from hotirjam_gateway.connection_manager import ConnectionManager
from hotirjam_gateway.connection_state import ConnectionState
from hotirjam_gateway.envelope import (
    DEFAULT_SENDER_ID,
    GATEWAY_PROTOCOL_VERSION,
    Channel,
    Envelope,
)
from hotirjam_gateway.health import HealthStatus
from hotirjam_gateway.heartbeat import HeartbeatMonitor
from hotirjam_gateway.lifecycle import Lifecycle, LifecycleError
from hotirjam_gateway.logging import get_logger, setup_logging

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_SENDER_ID",
    "GATEWAY_PROTOCOL_VERSION",
    "Channel",
    "ConnectionManager",
    "ConnectionState",
    "Envelope",
    "HealthStatus",
    "HeartbeatMonitor",
    "Lifecycle",
    "LifecycleError",
    "get_logger",
    "setup_logging",
    "__version__",
]
