"""M1.3 Bridge Receiver runtime tests — no network, no AI."""

from __future__ import annotations

import io
import json
import threading
import time
from pathlib import Path

from hotirjam_bridge.contracts import Channel, Envelope
from hotirjam_bridge.receiver.app import main
from hotirjam_bridge.receiver.integrity import (
    assert_payload_line_matches,
    canonical_payload_line,
    line_sha256,
)
from hotirjam_bridge.receiver.runtime import EnvelopeReceiverRuntime
from hotirjam_bridge.sender.envelope import wrap_tick

_TEST_SESSION = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_TEST_SENDER = "HOTIRJAM_WINDOWS_01"


def _tick_payload(i: int) -> dict:
    px = 18000.0 + (i % 17) * 0.25
    return {
        "timestamp": 1_700_000_000.0 + float(i),
        "symbol": "MNQ",
        "last_price": px,
        "bid": px - 0.25,
        "ask": px + 0.25,
        "volume": 1.0,
    }


def _dom_payload(i: int) -> dict:
    px = 18000.0 + i * 0.25
    return {
        "schema_version": "1.0",
        "timestamp_utc": f"2026-07-10T00:00:00.{i:06d}Z",
        "instrument": "MNQ",
        "bids": [{"price": px, "size": 1}],
        "asks": [{"price": px + 0.25, "size": 1}],
        "status": "OK",
    }


def test_integrity_byte_level_roundtrip() -> None:
    payload = _tick_payload(3)
    line = canonical_payload_line(payload)
    digest = assert_payload_line_matches(payload, line)
    assert digest == line_sha256(line)


def test_1000_ticks_written_in_seq_order(tmp_path: Path) -> None:
    log = io.StringIO()
    runtime = EnvelopeReceiverRuntime(out_dir=tmp_path / "out", log_stream=log)
    for i in range(1, 1001):
        env = wrap_tick(
            _tick_payload(i),
            seq=i,
            sent_at=float(i),
            sender_id=_TEST_SENDER,
            session_id=_TEST_SESSION,
        )
        assert runtime.accept(env) is True

    assert runtime.stats.accepted_tick == 1000
    assert runtime.accepted_seq_tick == list(range(1, 1001))
    lines = runtime.tick_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1000
    for i, line in enumerate(lines, start=1):
        payload = _tick_payload(i)
        assert_payload_line_matches(payload, line + "\n")
        assert json.loads(line) == payload


def test_duplicate_not_written(tmp_path: Path) -> None:
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
    )
    env = wrap_tick(
        _tick_payload(1),
        seq=1,
        sent_at=1.0,
        sender_id=_TEST_SENDER,
        session_id=_TEST_SESSION,
    )
    assert runtime.accept(env) is True
    assert runtime.accept(env) is False
    assert runtime.stats.duplicates == 1
    assert runtime.stats.accepted_tick == 1
    assert len(runtime.tick_path.read_text(encoding="utf-8").splitlines()) == 1


def test_malformed_envelope_rejected(tmp_path: Path) -> None:
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
    )
    assert runtime.accept_envelope_line("{not-json") is False
    assert runtime.accept_envelope_line('{"v":1,"ch":"tick"}') is False
    bad = Envelope(
        v=1,
        ch=Channel.TICK.value,
        seq=1,
        src="NT01",
        sent_at=1.0,
        payload={"symbol": "MNQ"},
        sender_id=_TEST_SENDER,
        session_id=_TEST_SESSION,
    )
    assert runtime.accept(bad) is False
    assert runtime.stats.malformed >= 3
    assert runtime.stats.accepted_tick == 0
    assert runtime.tick_path.read_text(encoding="utf-8") == ""


def test_dom_written_to_mnq_dom(tmp_path: Path) -> None:
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
    )
    env = Envelope(
        v=1,
        ch=Channel.DOM.value,
        seq=1,
        src="NT03",
        sent_at=1.0,
        payload=_dom_payload(0),
        sender_id=_TEST_SENDER,
        session_id=_TEST_SESSION,
    )
    assert runtime.accept(env) is True
    assert runtime.stats.accepted_dom == 1
    line = runtime.dom_path.read_text(encoding="utf-8")
    assert_payload_line_matches(_dom_payload(0), line)


def test_clean_stop_like_ctrl_c(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.ndjson"
    inbox.write_text("", encoding="utf-8")
    log = io.StringIO()
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=log,
        poll_interval=0.01,
        sleep=lambda _s: time.sleep(0.01),
    )

    def _stop_soon() -> None:
        time.sleep(0.05)
        runtime.request_stop()

    thread = threading.Thread(target=_stop_soon, daemon=True)
    thread.start()
    stats = runtime.run_inbox(inbox, start_at_eof=True)
    thread.join(timeout=2.0)
    assert "[BRIDGE_RECEIVER] stop" in log.getvalue()
    assert stats.accepted_tick == 0


def test_cli_inbox_max_messages(tmp_path: Path) -> None:
    out_dir = tmp_path / "HOTIRJAM"
    inbox = tmp_path / "envelopes.ndjson"
    with inbox.open("w", encoding="utf-8") as handle:
        for i in range(1, 6):
            env = wrap_tick(
                _tick_payload(i),
                seq=i,
                sent_at=float(i),
                sender_id=_TEST_SENDER,
                session_id=_TEST_SESSION,
            )
            handle.write(json.dumps(env.as_dict(), separators=(",", ":")) + "\n")
    log_file = tmp_path / "receiver_runtime.log"
    code = main(
        [
            "--out-dir",
            str(out_dir),
            "--inbox",
            str(inbox),
            "--from-start",
            "--max-messages",
            "5",
            "--poll",
            "0",
            "--log-file",
            str(log_file),
        ]
    )
    assert code == 0
    ticks = (out_dir / "mnq_ticks.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(ticks) == 5
    text = log_file.read_text(encoding="utf-8")
    assert "network=OFF" in text
    assert "sha256=" in text
    assert "ticks=5" in text
