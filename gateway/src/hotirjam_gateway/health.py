"""Health composite status for the HOTIRJAM Gateway."""

from __future__ import annotations

from enum import StrEnum


class HealthStatus(StrEnum):
    """Aggregate Gateway health (Phase 1 health rules)."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    STOPPED = "STOPPED"
