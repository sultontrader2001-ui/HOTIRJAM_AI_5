"""Async HTTP Bridge Receiver server (aiohttp)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, TextIO

from aiohttp import web

from hotirjam_bridge.metrics import BridgeMetrics, format_bridge_status, render_bridge_status
from hotirjam_bridge.receiver.runtime import EnvelopeReceiverRuntime
from hotirjam_bridge.receiver.validate_envelope import (
    EnvelopeValidationError,
    validate_envelope_dict,
)


def create_http_app(
    runtime: EnvelopeReceiverRuntime,
    metrics: BridgeMetrics,
) -> web.Application:
    """Build aiohttp app: /envelope /tick /dom /heartbeat /metrics /status /health."""

    async def post_envelope(request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            metrics.record_malformed()
            return web.json_response({"status": "error", "error": "invalid json"}, status=400)
        return _handle_envelope_dict(runtime, metrics, data)

    async def post_tick(request: web.Request) -> web.Response:
        return await post_envelope(request)

    async def post_dom(request: web.Request) -> web.Response:
        return await post_envelope(request)

    async def post_heartbeat(request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        metrics.record_heartbeat(ok=True)
        if isinstance(data, dict) and "tick_sent" in data:
            metrics.tick_sent = max(metrics.tick_sent, int(data["tick_sent"]))
        if isinstance(data, dict) and "dom_sent" in data:
            metrics.dom_sent = max(metrics.dom_sent, int(data["dom_sent"]))
        runtime._log(  # noqa: SLF001
            f"[BRIDGE_RECEIVER] heartbeat ok tick_sent={data.get('tick_sent') if isinstance(data, dict) else None} "
            f"dom_sent={data.get('dom_sent') if isinstance(data, dict) else None}"
        )
        return web.json_response({"status": "ok", "heartbeat": "OK"})

    async def get_metrics(_request: web.Request) -> web.Response:
        return web.json_response(metrics.as_dict())

    async def get_status(_request: web.Request) -> web.Response:
        text = format_bridge_status(metrics) + "\n"
        return web.Response(text=text, content_type="text/plain")

    async def get_health(_request: web.Request) -> web.Response:
        metrics.refresh_connected()
        return web.json_response(
            {
                "ok": True,
                "connected": metrics.connected,
                "heartbeat": "OK" if metrics.heartbeat_ok else "FAIL",
                "tick_received": metrics.tick_received,
                "dom_received": metrics.dom_received,
            }
        )

    app = web.Application()
    app.router.add_post("/envelope", post_envelope)
    app.router.add_post("/tick", post_tick)
    app.router.add_post("/dom", post_dom)
    app.router.add_post("/heartbeat", post_heartbeat)
    app.router.add_get("/metrics", get_metrics)
    app.router.add_get("/status", get_status)
    app.router.add_get("/health", get_health)
    return app


def _handle_envelope_dict(
    runtime: EnvelopeReceiverRuntime,
    metrics: BridgeMetrics,
    data: Any,
) -> web.Response:
    if not isinstance(data, dict):
        metrics.record_malformed()
        return web.json_response({"status": "error", "error": "object required"}, status=400)
    try:
        envelope = validate_envelope_dict(data)
    except EnvelopeValidationError as exc:
        metrics.record_malformed()
        return web.json_response({"status": "error", "error": str(exc)}, status=400)

    written = runtime.accept(envelope)
    return web.json_response(
        {
            "status": "ok",
            "written": written,
            "ch": envelope.ch,
            "seq": envelope.seq,
            "tick_received": metrics.tick_received,
            "dom_received": metrics.dom_received,
            "duplicate": metrics.duplicate,
            "dropped": metrics.dropped,
        }
    )


async def run_http_receiver(
    *,
    runtime: EnvelopeReceiverRuntime,
    metrics: BridgeMetrics,
    host: str = "0.0.0.0",
    port: int = 8765,
    status_interval: float = 0.5,
    status_stream: TextIO | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Serve HTTP bridge until stop_event is set."""
    app = create_http_app(runtime, metrics)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    runtime._log(  # noqa: SLF001
        f"[BRIDGE_RECEIVER] HTTP listen http://{host}:{port} "
        f"out_dir={runtime.out_dir} network=ON"
    )
    stop = stop_event or asyncio.Event()
    stream = status_stream if status_stream is not None else runtime.log_stream

    async def _status_loop() -> None:
        while not stop.is_set():
            render_bridge_status(metrics, stream, clear=True)
            try:
                await asyncio.wait_for(stop.wait(), timeout=status_interval)
            except asyncio.TimeoutError:
                continue

    status_task = asyncio.create_task(_status_loop())
    try:
        await stop.wait()
    finally:
        status_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await status_task
        await runner.cleanup()
        runtime._log(  # noqa: SLF001
            f"[BRIDGE_RECEIVER] HTTP stop ticks={metrics.tick_received} "
            f"dom={metrics.dom_received} dropped={metrics.dropped} "
            f"duplicate={metrics.duplicate}"
        )
        render_bridge_status(metrics, stream, clear=False)
