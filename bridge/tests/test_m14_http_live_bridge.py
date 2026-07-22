"""M1.4 HTTP live bridge tests — no AI imports."""

from __future__ import annotations

import io
import json
import socket
from pathlib import Path

import pytest
from aiohttp import web

from hotirjam_bridge.metrics import BridgeMetrics, format_bridge_status
from hotirjam_bridge.receiver.http_server import create_http_app
from hotirjam_bridge.receiver.runtime import EnvelopeReceiverRuntime
from hotirjam_bridge.sender.envelope import wrap_tick
from hotirjam_bridge.sender.http_client import BridgeHttpClient
from hotirjam_bridge.sender.http_runtime import HttpSenderRuntime


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _tick_line(i: int) -> str:
    px = 18000.0 + (i % 17) * 0.25
    payload = {
        "timestamp": 1_700_000_000.0 + float(i),
        "symbol": "MNQ",
        "last_price": px,
        "bid": px - 0.25,
        "ask": px + 0.25,
        "volume": 1.0,
    }
    return json.dumps(payload, separators=(",", ":")) + "\n"


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


def test_status_board_format() -> None:
    m = BridgeMetrics()
    m.tick_sent = 125432
    m.tick_received = 125432
    m.record_heartbeat(ok=True)
    text = format_bridge_status(m)
    assert "Bridge Status" in text
    assert "Connected: YES" in text
    assert "Tick Sent: 125432" in text
    assert "Tick Received: 125432" in text
    assert "Dropped: 0" in text
    assert "Duplicate: 0" in text
    assert "Latency Avg:" in text
    assert "Heartbeat: OK" in text


@pytest.mark.asyncio
async def test_http_1000_ticks_zero_loss_order_dom(tmp_path: Path) -> None:
    out_dir = tmp_path / "HOTIRJAM"
    metrics = BridgeMetrics()
    log = io.StringIO()
    runtime = EnvelopeReceiverRuntime(
        out_dir=out_dir,
        log_stream=log,
        metrics=metrics,
    )
    app = create_http_app(runtime, metrics)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()
    base_url = f"http://127.0.0.1:{port}"

    tick_file = tmp_path / "mnq_ticks.ndjson"
    dom_file = tmp_path / "mnq_dom.ndjson"
    with tick_file.open("w", encoding="utf-8") as handle:
        for i in range(1, 1001):
            handle.write(_tick_line(i))
    with dom_file.open("w", encoding="utf-8") as handle:
        for i in range(1, 11):
            handle.write(json.dumps(_dom_payload(i), separators=(",", ":")) + "\n")

    sender_log = io.StringIO()
    sender = HttpSenderRuntime(
        tick_file=tick_file,
        dom_file=dom_file,
        base_url=base_url,
        start_at_eof=False,
        max_ticks=1000,
        poll_interval=0.0,
        heartbeat_interval=0.05,
        status_interval=10.0,
        log_stream=sender_log,
        timeout=2.0,
        max_retries=3,
    )
    result = await sender.run()
    await runner.cleanup()

    assert result.tick_sent == 1000
    assert metrics.tick_received == 1000
    assert metrics.dropped == 0
    assert metrics.duplicate == 0
    assert metrics.dom_received == 10
    assert runtime.accepted_seq_tick == list(range(1, 1001))

    lines = (out_dir / "mnq_ticks.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1000
    for i, line in enumerate(lines, start=1):
        assert json.loads(line)["timestamp"] == 1_700_000_000.0 + float(i)

    dom_lines = (out_dir / "mnq_dom.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(dom_lines) == 10
    assert json.loads(dom_lines[0])["instrument"] == "MNQ"
    assert "Bridge Status" in sender_log.getvalue()
    assert "Tick Sent:" in sender_log.getvalue()


@pytest.mark.asyncio
async def test_http_duplicate_and_heartbeat(tmp_path: Path) -> None:
    metrics = BridgeMetrics()
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
        metrics=metrics,
    )
    app = create_http_app(runtime, metrics)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    base = f"http://127.0.0.1:{port}"

    env = wrap_tick(
        {
            "timestamp": 1.0,
            "symbol": "MNQ",
            "last_price": 1.0,
            "bid": 1.0,
            "ask": 1.25,
            "volume": 1.0,
        },
        seq=1,
        sent_at=1.0,
    )
    async with BridgeHttpClient(base) as client:
        await client.post_envelope(env)
        await client.post_envelope(env)
        await client.post_heartbeat(tick_sent=1, dom_sent=0)
        remote = await client.get_metrics()

    await runner.cleanup()
    assert remote["tick_received"] == 1
    assert remote["duplicate"] == 1
    assert remote["heartbeat_ok"] is True
    assert metrics.tick_sent >= 1


@pytest.mark.asyncio
async def test_sequence_gap_counts_dropped(tmp_path: Path) -> None:
    metrics = BridgeMetrics()
    runtime = EnvelopeReceiverRuntime(
        out_dir=tmp_path / "out",
        log_stream=io.StringIO(),
        metrics=metrics,
    )
    app = create_http_app(runtime, metrics)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    base = f"http://127.0.0.1:{port}"

    def env(seq: int):
        return wrap_tick(
            {
                "timestamp": float(seq),
                "symbol": "MNQ",
                "last_price": 1.0,
                "bid": 1.0,
                "ask": 1.25,
                "volume": 1.0,
            },
            seq=seq,
            sent_at=float(seq),
        )

    async with BridgeHttpClient(base) as client:
        await client.post_envelope(env(1))
        await client.post_envelope(env(3))

    await runner.cleanup()
    assert metrics.tick_received == 2
    assert metrics.dropped == 1
