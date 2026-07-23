"""Envelope Identity v2 — session-scoped dedupe contract tests."""

from __future__ import annotations

import io
import json
from pathlib import Path

from hotirjam_bridge.receiver.runtime import EnvelopeReceiverRuntime
from hotirjam_bridge.sender.envelope import wrap_tick
from hotirjam_bridge.sender.http_runtime import HttpSenderRuntime


def _tick(i: int) -> dict:
    px = 18000.0 + float(i) * 0.25
    return {
        "timestamp": 1_700_000_000.0 + float(i),
        "symbol": "MNQ",
        "last_price": px,
        "bid": px - 0.25,
        "ask": px + 0.25,
        "volume": 1.0,
    }


def test_retry_same_session_seq_is_deduplicated(tmp_path: Path) -> None:
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
    )
    env = wrap_tick(
        _tick(1),
        seq=1,
        sent_at=1.0,
        sender_id="HOTIRJAM_WINDOWS_01",
        session_id="11111111-1111-4111-8111-111111111111",
    )
    assert runtime.accept(env) is True
    assert runtime.accept(env) is False
    assert runtime.stats.accepted_tick == 1
    assert runtime.stats.duplicates == 1
    assert len(runtime.tick_path.read_text(encoding="utf-8").splitlines()) == 1


def test_sender_restart_new_session_accepts_seq_1(tmp_path: Path) -> None:
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
    )
    session_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    session_b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    first = wrap_tick(
        _tick(1),
        seq=1,
        sent_at=1.0,
        sender_id="HOTIRJAM_WINDOWS_01",
        session_id=session_a,
    )
    assert runtime.accept(first) is True

    # Simulate sender restart: new session_id, seq restarts at 1.
    restarted = wrap_tick(
        _tick(2),
        seq=1,
        sent_at=2.0,
        sender_id="HOTIRJAM_WINDOWS_01",
        session_id=session_b,
    )
    assert runtime.accept(restarted) is True
    assert runtime.stats.accepted_tick == 2
    assert runtime.stats.duplicates == 0
    lines = runtime.tick_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["last_price"] == 18000.25
    assert json.loads(lines[1])["last_price"] == 18000.5


def test_old_session_still_deduplicates_after_new_session(tmp_path: Path) -> None:
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
    )
    session_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    session_b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    env_a = wrap_tick(
        _tick(1),
        seq=1,
        sent_at=1.0,
        sender_id="HOTIRJAM_WINDOWS_01",
        session_id=session_a,
    )
    assert runtime.accept(env_a) is True

    env_b = wrap_tick(
        _tick(2),
        seq=1,
        sent_at=2.0,
        sender_id="HOTIRJAM_WINDOWS_01",
        session_id=session_b,
    )
    assert runtime.accept(env_b) is True

    # Retry of old session envelope must still be rejected.
    assert runtime.accept(env_a) is False
    assert runtime.stats.duplicates == 1
    assert runtime.stats.accepted_tick == 2
    assert len(runtime.tick_path.read_text(encoding="utf-8").splitlines()) == 2


def test_http_sender_generates_session_id_once(tmp_path: Path) -> None:
    tick_file = tmp_path / "mnq_ticks.ndjson"
    tick_file.write_text("", encoding="utf-8")
    a = HttpSenderRuntime(
        tick_file=tick_file,
        base_url="http://127.0.0.1:9",
        session_id=None,
    )
    b = HttpSenderRuntime(
        tick_file=tick_file,
        base_url="http://127.0.0.1:9",
        session_id=None,
    )
    assert a.session_id
    assert b.session_id
    assert a.session_id != b.session_id
    assert len(str(a.session_id)) == 36
