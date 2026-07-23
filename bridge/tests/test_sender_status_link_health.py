"""Sender status must reflect link health from GET /metrics, not receiver idle flags."""

from __future__ import annotations

from hotirjam_bridge.metrics import BridgeMetrics, format_bridge_status


def test_merge_remote_does_not_copy_receiver_connected_flags() -> None:
    m = BridgeMetrics()
    m.connected = True
    m.heartbeat_ok = True
    m.merge_remote(
        {
            "tick_received": 42,
            "connected": False,
            "heartbeat_ok": False,
            "dropped": 0,
            "duplicate": 0,
        }
    )
    assert m.tick_received == 42
    assert m.connected is True
    assert m.heartbeat_ok is True


def test_format_status_does_not_wipe_connected_without_refresh() -> None:
    m = BridgeMetrics()
    m.touch_activity()
    m.connected = True
    m.heartbeat_ok = False
    text = format_bridge_status(m, refresh=False)
    assert "Connected: YES" in text
    assert "Heartbeat: FAIL" in text


def test_metrics_poll_semantics_like_sender_refresh() -> None:
    """Mirrors fixed _refresh_status: metrics OK ⇒ Connected YES."""
    local = BridgeMetrics()
    remote = {
        "tick_received": 0,
        "dom_received": 0,
        "dropped": 0,
        "duplicate": 0,
        "connected": False,
        "heartbeat_ok": False,
        "latency_avg_ms": None,
    }
    local.merge_remote(remote)
    local.touch_activity()
    local.connected = True
    # No local heartbeat yet
    assert local.last_hb_at is None
    text = format_bridge_status(local, refresh=False)
    assert "Connected: YES" in text
