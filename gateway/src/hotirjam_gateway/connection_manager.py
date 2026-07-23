"""Connection manager skeleton (Sprint 1 — no network I/O)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from hotirjam_gateway.connection_state import ConnectionState
from hotirjam_gateway.envelope import DEFAULT_SENDER_ID
from hotirjam_gateway.health import HealthStatus
from hotirjam_gateway.heartbeat import HeartbeatMonitor
from hotirjam_gateway.lifecycle import Lifecycle, LifecycleError
from hotirjam_gateway.logging import get_logger

_log = get_logger(__name__)


@dataclass
class ConnectionManager:
    """Own lifecycle + heartbeat for one Gateway session (skeleton).

    Sprint 1 does not open sockets. Methods advance local state only so unit
    tests and later transport wiring share one control surface.
    """

    sender_id: str = DEFAULT_SENDER_ID
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lifecycle: Lifecycle = field(default_factory=Lifecycle)
    heartbeat: HeartbeatMonitor = field(default_factory=HeartbeatMonitor)
    _stream_alive: bool = False

    def __post_init__(self) -> None:
        self.sender_id = str(self.sender_id or DEFAULT_SENDER_ID)
        if not self.session_id:
            self.session_id = str(uuid.uuid4())

    @property
    def state(self) -> ConnectionState:
        return self.lifecycle.state

    def health(self) -> HealthStatus:
        """Composite health from lifecycle + heartbeat (+ stream flag)."""
        if self.state is ConnectionState.STOPPED:
            return HealthStatus.STOPPED
        if self.state in {
            ConnectionState.DISCONNECTED,
            ConnectionState.CONNECTING,
            ConnectionState.RECONNECTING,
        }:
            return HealthStatus.UNHEALTHY

        hb = self.heartbeat.health_contribution()
        if self.state is ConnectionState.DEGRADED:
            return HealthStatus.DEGRADED
        if hb is HealthStatus.UNHEALTHY:
            return HealthStatus.UNHEALTHY
        if hb is HealthStatus.DEGRADED or not self._stream_alive:
            if self.state is ConnectionState.READY and hb is HealthStatus.HEALTHY:
                # Link ready, waiting for market — not unhealthy.
                return HealthStatus.HEALTHY
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def start_connect(self) -> ConnectionState:
        """DISCONNECTED → CONNECTING."""
        state = self.lifecycle.transition(
            ConnectionState.CONNECTING,
            reason="start_connect",
        )
        _log.info(
            "connect_started",
            extra={
                "gateway_event": "connect_started",
                "sender_id": self.sender_id,
                "session_id": self.session_id,
            },
        )
        return state

    def mark_ready(self) -> ConnectionState:
        """CONNECTING | RECONNECTING → READY after successful HELLO path."""
        if self.state is ConnectionState.RECONNECTING:
            return self.lifecycle.transition(
                ConnectionState.READY,
                reason="reconnect_ready",
            )
        return self.lifecycle.transition(ConnectionState.READY, reason="hello_ack")

    def mark_streaming(self) -> ConnectionState:
        """READY | DEGRADED → STREAMING when market data is flowing."""
        self._stream_alive = True
        return self.lifecycle.transition(
            ConnectionState.STREAMING,
            reason="stream_alive",
        )

    def mark_degraded(self, *, reason: str = "degraded") -> ConnectionState:
        self._stream_alive = False
        return self.lifecycle.transition(ConnectionState.DEGRADED, reason=reason)

    def start_reconnect(self, *, reason: str = "link_lost") -> ConnectionState:
        self._stream_alive = False
        self.heartbeat.reset()
        return self.lifecycle.transition(
            ConnectionState.RECONNECTING,
            reason=reason,
        )

    def mark_disconnected(self, *, reason: str = "disconnected") -> ConnectionState:
        self._stream_alive = False
        return self.lifecycle.transition(
            ConnectionState.DISCONNECTED,
            reason=reason,
        )

    def stop(self) -> ConnectionState:
        """Enter terminal STOPPED."""
        self._stream_alive = False
        return self.lifecycle.transition(ConnectionState.STOPPED, reason="operator_stop")

    def record_heartbeat(self) -> None:
        """Skeleton hook: record local heartbeat success."""
        self.heartbeat.record_success()

    def new_session(self) -> str:
        """Mint a new session_id (e.g. after process-level restart semantics)."""
        if self.state not in {
            ConnectionState.DISCONNECTED,
            ConnectionState.STOPPED,
            ConnectionState.RECONNECTING,
        }:
            raise LifecycleError(
                f"new_session not allowed in state {self.state.value}"
            )
        self.session_id = str(uuid.uuid4())
        self.heartbeat.reset()
        self._stream_alive = False
        _log.info(
            "session_renewed",
            extra={
                "gateway_event": "session_renewed",
                "sender_id": self.sender_id,
                "session_id": self.session_id,
            },
        )
        return self.session_id
