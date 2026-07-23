"""Evidence instrumentation for BridgeHttpClient — behaviour unchanged."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aiohttp import web

from hotirjam_bridge.contracts import (
    BRIDGE_PROTOCOL_VERSION,
    Channel,
    Envelope,
    SourceTag,
)
from hotirjam_bridge.sender.http_client import BridgeHttpClient


async def _run_app(handler: Any) -> tuple[str, web.AppRunner]:
    app = web.Application()
    app.router.add_post("/tick", handler)
    app.router.add_post("/heartbeat", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None  # noqa: SLF001
    sockets = site._server.sockets
    assert sockets is not None and sockets
    port = sockets[0].getsockname()[1]
    return f"http://127.0.0.1:{port}", runner


def _tick_env(seq: int) -> Envelope:
    return Envelope(
        v=BRIDGE_PROTOCOL_VERSION,
        ch=Channel.TICK.value,
        seq=seq,
        src=SourceTag.NT01.value,
        sent_at=1.0,
        payload={
            "timestamp": 1.0,
            "symbol": "MNQ",
            "last_price": 100.0,
            "bid": 99.75,
            "ask": 100.0,
            "volume": 1.0,
        },
    )


def test_tick_post_evidence_logs_written_true(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def _main() -> None:
        async def ok(request: web.Request) -> web.Response:
            data = await request.json()
            return web.json_response(
                {
                    "status": "ok",
                    "written": True,
                    "ch": "tick",
                    "seq": data.get("seq"),
                }
            )

        base, runner = await _run_app(ok)
        try:
            async with BridgeHttpClient(base, timeout=2.0, max_retries=1) as client:
                body = await client.post_envelope(_tick_env(42))
            assert body["written"] is True
        finally:
            await runner.cleanup()

    asyncio.run(_main())
    err = capsys.readouterr().err
    assert "[BRIDGE_SENDER_EVIDENCE][TICK]" in err
    assert "http_status=200" in err
    assert "written=True" in err
    assert "exception=None" in err
    assert "duration_ms=" in err


def test_tick_post_evidence_logs_written_false(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def _main() -> None:
        async def dup(_request: web.Request) -> web.Response:
            return web.json_response(
                {
                    "status": "ok",
                    "written": False,
                    "ch": "tick",
                    "seq": 1,
                    "duplicate": 1,
                }
            )

        base, runner = await _run_app(dup)
        try:
            async with BridgeHttpClient(base, timeout=2.0, max_retries=1) as client:
                body = await client.post_envelope(_tick_env(1))
            assert body["written"] is False
        finally:
            await runner.cleanup()

    asyncio.run(_main())
    err = capsys.readouterr().err
    assert "[BRIDGE_SENDER_EVIDENCE][TICK]" in err
    assert "http_status=200" in err
    assert "written=False" in err


def test_heartbeat_evidence_logs_separately(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def _main() -> None:
        async def ok(_request: web.Request) -> web.Response:
            return web.json_response({"status": "ok", "heartbeat": "OK"})

        base, runner = await _run_app(ok)
        try:
            async with BridgeHttpClient(base, timeout=2.0, max_retries=1) as client:
                await client.post_heartbeat(tick_sent=3, dom_sent=0)
        finally:
            await runner.cleanup()

    asyncio.run(_main())
    err = capsys.readouterr().err
    assert "[BRIDGE_SENDER_EVIDENCE][HEARTBEAT]" in err
    assert "http_status=200" in err
    assert "[BRIDGE_SENDER_EVIDENCE][TICK]" not in err


def test_tick_timeout_evidence_logs_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def _main() -> None:
        async def hang(_request: web.Request) -> web.Response:
            await asyncio.sleep(5.0)
            return web.json_response({"status": "ok", "written": True})

        base, runner = await _run_app(hang)
        try:
            async with BridgeHttpClient(base, timeout=0.2, max_retries=1) as client:
                with pytest.raises(Exception):
                    await client.post_envelope(_tick_env(7))
        finally:
            await runner.cleanup()

    asyncio.run(_main())
    err = capsys.readouterr().err
    assert "[BRIDGE_SENDER_EVIDENCE][TICK]" in err
    assert "exception=" in err
    assert "duration_ms=" in err
    assert (
        "Timeout" in err
        or "timeout" in err.lower()
        or "Cancelled" in err
        or "Client" in err
    )
