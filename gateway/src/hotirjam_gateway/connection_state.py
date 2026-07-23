"""Connection lifecycle states for the HOTIRJAM Gateway link."""

from __future__ import annotations

from enum import StrEnum


class ConnectionState(StrEnum):
    """Gateway link states (Phase 1 connection architecture)."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    READY = "READY"
    STREAMING = "STREAMING"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    STOPPED = "STOPPED"
