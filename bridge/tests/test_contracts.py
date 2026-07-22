"""Contract tests for bridge design module — no network, no AI."""

from __future__ import annotations

from hotirjam_bridge.contracts import (
    BRIDGE_PROTOCOL_VERSION,
    NT01_REQUIRED_KEYS,
    NT03_REQUIRED_KEYS,
    Channel,
    Envelope,
)
from hotirjam_bridge.receiver import ReceiverConfig
from hotirjam_bridge.sender import SenderConfig
from pathlib import Path


def test_protocol_version_locked() -> None:
    assert BRIDGE_PROTOCOL_VERSION == 1


def test_envelope_roundtrip() -> None:
    env = Envelope(
        v=1,
        ch=Channel.TICK.value,
        seq=7,
        src="NT01",
        sent_at=1710000000.5,
        payload={
            "timestamp": 1710000000.1,
            "symbol": "MNQ",
            "last_price": 1.0,
            "bid": 1.0,
            "ask": 1.25,
            "volume": 1.0,
        },
    )
    restored = Envelope.from_dict(env.as_dict())
    assert restored == env
    assert NT01_REQUIRED_KEYS <= restored.payload.keys()


def test_nt03_required_keys_documented() -> None:
    assert "bids" in NT03_REQUIRED_KEYS
    assert "asks" in NT03_REQUIRED_KEYS


def test_sender_receiver_config_shapes() -> None:
    sender = SenderConfig(
        tick_file=Path("mnq_ticks.ndjson"),
        dom_file=Path("mnq_dom.ndjson"),
        receiver_url="wss://127.0.0.1:9443/bridge",
    )
    receiver = ReceiverConfig(out_dir=Path("/tmp/HOTIRJAM"))
    assert sender.mode == "log-only"
    assert receiver.wss_port == 9443
