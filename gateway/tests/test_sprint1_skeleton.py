"""Sprint 1 Gateway skeleton tests — no network, no AI."""

from __future__ import annotations

import logging

import pytest

from hotirjam_gateway import (
    DEFAULT_SENDER_ID,
    GATEWAY_PROTOCOL_VERSION,
    Channel,
    ConnectionManager,
    ConnectionState,
    Envelope,
    HealthStatus,
    HeartbeatMonitor,
    Lifecycle,
    LifecycleError,
    get_logger,
    setup_logging,
)


def test_connection_state_values() -> None:
    assert ConnectionState.DISCONNECTED.value == "DISCONNECTED"
    assert ConnectionState.STREAMING in ConnectionState


def test_health_status_values() -> None:
    assert HealthStatus.HEALTHY.value == "HEALTHY"
    assert set(HealthStatus) == {
        HealthStatus.HEALTHY,
        HealthStatus.DEGRADED,
        HealthStatus.UNHEALTHY,
        HealthStatus.STOPPED,
    }


def test_envelope_roundtrip_identity_v2() -> None:
    env = Envelope(
        v=GATEWAY_PROTOCOL_VERSION,
        ch=Channel.TICK.value,
        seq=1,
        src="NT01",
        sent_at=1.0,
        payload={"symbol": "MNQ", "last_price": 1.0},
        sender_id=DEFAULT_SENDER_ID,
        session_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    restored = Envelope.from_dict(env.as_dict())
    assert restored == env
    assert restored.dedupe_key() == (
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "tick",
        1,
    )


def test_lifecycle_happy_path() -> None:
    life = Lifecycle()
    assert life.state is ConnectionState.DISCONNECTED
    life.transition(ConnectionState.CONNECTING)
    life.transition(ConnectionState.READY)
    life.transition(ConnectionState.STREAMING)
    life.transition(ConnectionState.DEGRADED)
    life.transition(ConnectionState.RECONNECTING)
    life.transition(ConnectionState.READY)
    life.transition(ConnectionState.STOPPED)
    assert life.state is ConnectionState.STOPPED


def test_lifecycle_rejects_illegal_transition() -> None:
    life = Lifecycle()
    with pytest.raises(LifecycleError):
        life.transition(ConnectionState.STREAMING)


def test_lifecycle_stopped_is_terminal() -> None:
    life = Lifecycle()
    life.transition(ConnectionState.CONNECTING)
    life.transition(ConnectionState.STOPPED)
    with pytest.raises(LifecycleError):
        life.transition(ConnectionState.CONNECTING)
    with pytest.raises(LifecycleError):
        life.reset()


def test_heartbeat_monitor_freshness() -> None:
    clock = {"t": 100.0}

    def now() -> float:
        return clock["t"]

    hb = HeartbeatMonitor(interval_s=1.0, stale_after_s=5.0, clock=now)
    assert hb.is_ok() is False
    assert hb.health_contribution() is HealthStatus.UNHEALTHY

    hb.record_success()
    assert hb.is_ok() is True
    assert hb.health_contribution() is HealthStatus.HEALTHY

    clock["t"] = 106.0
    assert hb.is_ok() is False
    assert hb.health_contribution() is HealthStatus.DEGRADED


def test_connection_manager_skeleton_flow() -> None:
    mgr = ConnectionManager(sender_id="HOTIRJAM_WINDOWS_01")
    assert mgr.state is ConnectionState.DISCONNECTED
    assert mgr.health() is HealthStatus.UNHEALTHY

    mgr.start_connect()
    assert mgr.state is ConnectionState.CONNECTING

    mgr.mark_ready()
    mgr.record_heartbeat()
    assert mgr.state is ConnectionState.READY
    assert mgr.health() is HealthStatus.HEALTHY

    mgr.mark_streaming()
    assert mgr.state is ConnectionState.STREAMING
    assert mgr.health() is HealthStatus.HEALTHY

    mgr.mark_degraded(reason="tick_stale")
    assert mgr.state is ConnectionState.DEGRADED
    assert mgr.health() is HealthStatus.DEGRADED

    mgr.start_reconnect()
    assert mgr.state is ConnectionState.RECONNECTING
    sid = mgr.session_id
    new_sid = mgr.new_session()
    assert new_sid != sid

    mgr.mark_ready()
    mgr.stop()
    assert mgr.state is ConnectionState.STOPPED
    assert mgr.health() is HealthStatus.STOPPED


def test_structured_logging_setup() -> None:
    logger = setup_logging(level=logging.DEBUG, force=True)
    assert logger.name == "hotirjam_gateway"
    child = get_logger("lifecycle")
    assert child.name == "hotirjam_gateway.lifecycle"
    child.info("test_event", extra={"gateway_event": "test_event"})


def test_package_has_no_ai_import() -> None:
    import hotirjam_gateway
    import hotirjam_gateway.connection_manager as cm
    import hotirjam_gateway.envelope as env
    import hotirjam_gateway.lifecycle as lc

    for mod in (hotirjam_gateway, cm, env, lc):
        assert "hotirjam_ai5" not in dir(mod)
        assert not any(
            name.startswith("hotirjam_ai5") for name in getattr(mod, "__dict__", {})
        )
