"""Async HTTP Bridge Sender client (aiohttp) — retry + timeout."""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any

import aiohttp

from hotirjam_bridge.contracts import Channel, Envelope


class BridgeHttpClient:
    """POST envelopes to Mac Bridge Receiver."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 2.0,
        max_retries: int = 3,
        retry_delay: float = 0.2,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max(1, int(max_retries))
        self.retry_delay = max(0.0, float(retry_delay))
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> BridgeHttpClient:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
            self._owns_session = True
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def post_envelope(self, envelope: Envelope) -> dict[str, Any]:
        path = "/envelope"
        if envelope.ch == Channel.TICK.value:
            path = "/tick"
        elif envelope.ch == Channel.DOM.value:
            path = "/dom"
        elif envelope.ch == Channel.HB.value:
            path = "/heartbeat"
        return await self._post_json(path, envelope.as_dict())

    async def post_heartbeat(
        self,
        *,
        tick_sent: int,
        dom_sent: int = 0,
    ) -> dict[str, Any]:
        return await self._post_json(
            "/heartbeat",
            {"tick_sent": tick_sent, "dom_sent": dom_sent, "role": "sender"},
        )

    async def get_metrics(self) -> dict[str, Any]:
        assert self._session is not None
        url = f"{self.base_url}/metrics"
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if not isinstance(data, dict):
                raise RuntimeError("metrics response must be object")
            return data

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert self._session is not None
        url = f"{self.base_url}{path}"
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        payload_bytes = len(raw.encode("utf-8"))
        # TEMP runtime debug — remove after POST failures diagnosed
        print(
            f"[BRIDGE_SENDER_DEBUG] POST url={url} payload_bytes={payload_bytes}",
            file=sys.stderr,
            flush=True,
        )
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._session.post(url, json=payload) as resp:
                    body = await resp.json(content_type=None)
                    if resp.status >= 400:
                        raise RuntimeError(f"HTTP {resp.status}: {body}")
                    if not isinstance(body, dict):
                        return {"status": "ok"}
                    return body
            except Exception as exc:  # noqa: BLE001 — retry transport errors
                last_error = exc
                print(
                    f"[BRIDGE_SENDER_DEBUG] POST_FAIL attempt={attempt}/{self.max_retries} "
                    f"url={url} payload_bytes={payload_bytes} "
                    f"exc_type={type(exc).__name__} exc={exc!r}",
                    file=sys.stderr,
                    flush=True,
                )
                traceback.print_exc(file=sys.stderr)
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_delay * attempt)
        assert last_error is not None
        raise last_error
