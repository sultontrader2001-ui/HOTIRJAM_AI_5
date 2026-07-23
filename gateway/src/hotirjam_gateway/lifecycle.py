"""Connection lifecycle state machine (Sprint 1).

No network I/O. Pure transition rules from Phase 1 Gateway architecture.
"""

from __future__ import annotations

from hotirjam_gateway.connection_state import ConnectionState
from hotirjam_gateway.logging import get_logger

_log = get_logger(__name__)

# Legal directed edges: from → frozenset of allowed next states.
_TRANSITIONS: dict[ConnectionState, frozenset[ConnectionState]] = {
    ConnectionState.DISCONNECTED: frozenset(
        {
            ConnectionState.CONNECTING,
            ConnectionState.STOPPED,
        }
    ),
    ConnectionState.CONNECTING: frozenset(
        {
            ConnectionState.READY,
            ConnectionState.DISCONNECTED,
            ConnectionState.STOPPED,
        }
    ),
    ConnectionState.READY: frozenset(
        {
            ConnectionState.STREAMING,
            ConnectionState.DEGRADED,
            ConnectionState.RECONNECTING,
            ConnectionState.DISCONNECTED,
            ConnectionState.STOPPED,
        }
    ),
    ConnectionState.STREAMING: frozenset(
        {
            ConnectionState.DEGRADED,
            ConnectionState.RECONNECTING,
            ConnectionState.READY,
            ConnectionState.DISCONNECTED,
            ConnectionState.STOPPED,
        }
    ),
    ConnectionState.DEGRADED: frozenset(
        {
            ConnectionState.STREAMING,
            ConnectionState.READY,
            ConnectionState.RECONNECTING,
            ConnectionState.DISCONNECTED,
            ConnectionState.STOPPED,
        }
    ),
    ConnectionState.RECONNECTING: frozenset(
        {
            ConnectionState.READY,
            ConnectionState.DISCONNECTED,
            ConnectionState.STOPPED,
        }
    ),
    ConnectionState.STOPPED: frozenset(),
}


class LifecycleError(ValueError):
    """Illegal lifecycle transition."""


class Lifecycle:
    """Finite state machine for Gateway connection lifecycle."""

    def __init__(
        self,
        initial: ConnectionState = ConnectionState.DISCONNECTED,
    ) -> None:
        self._state = ConnectionState(initial)

    @property
    def state(self) -> ConnectionState:
        return self._state

    def can_transition(self, target: ConnectionState) -> bool:
        target = ConnectionState(target)
        if self._state is ConnectionState.STOPPED:
            return False
        if target is self._state:
            return True
        return target in _TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: ConnectionState, *, reason: str = "") -> ConnectionState:
        """Move to ``target`` or raise ``LifecycleError``."""
        target = ConnectionState(target)
        if target is self._state:
            return self._state
        if not self.can_transition(target):
            raise LifecycleError(
                f"illegal transition {self._state.value} → {target.value}"
                + (f" ({reason})" if reason else "")
            )
        previous = self._state
        self._state = target
        _log.info(
            "lifecycle_transition",
            extra={
                "gateway_event": "lifecycle_transition",
                "from_state": previous.value,
                "to_state": target.value,
                "reason": reason or None,
            },
        )
        return self._state

    def reset(self) -> None:
        """Return to DISCONNECTED unless STOPPED (terminal until new instance)."""
        if self._state is ConnectionState.STOPPED:
            raise LifecycleError("cannot reset from STOPPED; create a new Lifecycle")
        previous = self._state
        self._state = ConnectionState.DISCONNECTED
        if previous is not ConnectionState.DISCONNECTED:
            _log.info(
                "lifecycle_reset",
                extra={
                    "gateway_event": "lifecycle_reset",
                    "from_state": previous.value,
                    "to_state": ConnectionState.DISCONNECTED.value,
                },
            )
