"""HTTP Sender runtime — tail NDJSON, POST envelopes, status board."""

from __future__ import annotations

import asyncio
import json as _json
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from hotirjam_bridge.contracts import DEFAULT_SENDER_ID, Channel, Envelope
from hotirjam_bridge.metrics import BridgeMetrics, render_bridge_status
from hotirjam_bridge.receiver.validate_dom import DomValidationError, validate_nt03_dom
from hotirjam_bridge.sender.envelope import wrap_dom, wrap_tick
from hotirjam_bridge.sender.http_client import BridgeHttpClient
from hotirjam_bridge.sender.tail import NdjsonTail
from hotirjam_bridge.sender.validate_tick import (
    TickValidationError,
    parse_tick_json,
    validate_nt01_tick,
)


@dataclass
class HttpSenderRuntime:
    """M1.4 async HTTP sender (ticks + optional DOM)."""

    tick_file: Path
    base_url: str
    symbol: str = "MNQ"
    sender_id: str = DEFAULT_SENDER_ID
    session_id: str | None = None
    dom_file: Path | None = None
    poll_interval: float = 0.05
    start_at_eof: bool = True
    max_ticks: int | None = None
    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 0.2
    heartbeat_interval: float = 1.0
    status_interval: float = 0.5
    log_stream: TextIO = field(default_factory=lambda: sys.stdout)
    metrics: BridgeMetrics = field(default_factory=BridgeMetrics)
    clock: Callable[[], float] = field(default=time.time)

    def __post_init__(self) -> None:
        self.tick_file = Path(self.tick_file)
        self.dom_file = Path(self.dom_file) if self.dom_file else None
        self.sender_id = str(self.sender_id or DEFAULT_SENDER_ID)
        # Identity v2: one UUID4 per process lifetime (injectable for tests).
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        self._stop = False
        self._tick_tail = NdjsonTail(self.tick_file, start_at_eof=self.start_at_eof)
        self._dom_tail = (
            NdjsonTail(self.dom_file, start_at_eof=self.start_at_eof)
            if self.dom_file
            else None
        )
        self._tick_seq = 0
        self._dom_seq = 0

    def request_stop(self) -> None:
        self._stop = True

    async def run(self) -> BridgeMetrics:
        tick_size = (
            self.tick_file.stat().st_size if self.tick_file.is_file() else -1
        )
        dom_size = (
            self.dom_file.stat().st_size
            if self.dom_file is not None and self.dom_file.is_file()
            else -1
        )
        self._log(
            f"[BRIDGE_SENDER] HTTP start url={self.base_url} "
            f"sender_id={self.sender_id} session_id={self.session_id} "
            f"tick_file={self.tick_file} tick_size={tick_size} "
            f"tick_offset={self._tick_tail.offset} "
            f"dom_file={self.dom_file} dom_size={dom_size} "
            f"dom_offset={self._dom_tail.offset if self._dom_tail else None} "
            f"network=ON"
        )
        last_hb = 0.0
        last_status = 0.0
        async with BridgeHttpClient(
            self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
        ) as client:
            try:
                while not self._stop:
                    if self.max_ticks is not None and self.metrics.tick_sent >= self.max_ticks:
                        break
                    await self._poll_ticks(client)
                    await self._poll_dom(client)
                    now = float(self.clock())
                    if now - last_hb >= self.heartbeat_interval:
                        await self._heartbeat(client)
                        last_hb = now
                    if now - last_status >= self.status_interval:
                        await self._refresh_status(client)
                        last_status = now
                    if self.max_ticks is not None and self.metrics.tick_sent >= self.max_ticks:
                        break
                    await asyncio.sleep(self.poll_interval)
            finally:
                await self._refresh_status(client, clear=False)
                self._log(
                    f"[BRIDGE_SENDER] HTTP stop sent={self.metrics.tick_sent} "
                    f"received={self.metrics.tick_received} "
                    f"dropped={self.metrics.dropped} "
                    f"duplicate={self.metrics.duplicate}"
                )
        return self.metrics

    async def _poll_ticks(self, client: BridgeHttpClient) -> None:
        for line in self._tick_tail.poll():
            if self._stop:
                return
            if self.max_ticks is not None and self.metrics.tick_sent >= self.max_ticks:
                return
            try:
                payload = validate_nt01_tick(
                    parse_tick_json(line),
                    expected_symbol=self.symbol,
                )
            except TickValidationError as exc:
                self._log(f"[BRIDGE_SENDER] MALFORMED {exc}")
                continue
            self._tick_seq += 1
            envelope = wrap_tick(
                payload,
                seq=self._tick_seq,
                sender_id=self.sender_id,
                session_id=str(self.session_id),
                clock=self.clock,
            )
            await self._send(client, envelope)

    async def _poll_dom(self, client: BridgeHttpClient) -> None:
        if self._dom_tail is None:
            return
        for line in self._dom_tail.poll():
            if self._stop:
                return
            try:
                payload = _json.loads(line)
                if not isinstance(payload, dict):
                    raise DomValidationError("DOM payload must be object")
                validate_nt03_dom(payload, expected_symbol=self.symbol)
            except (DomValidationError, _json.JSONDecodeError, TypeError) as exc:
                self._log(f"[BRIDGE_SENDER] MALFORMED_DOM {exc}")
                continue
            self._dom_seq += 1
            envelope = wrap_dom(
                payload,
                seq=self._dom_seq,
                sender_id=self.sender_id,
                session_id=str(self.session_id),
                clock=self.clock,
            )
            await self._send(client, envelope)

    async def _send(self, client: BridgeHttpClient, envelope: Envelope) -> None:
        try:
            await client.post_envelope(envelope)
        except Exception as exc:  # noqa: BLE001
            self.metrics.record_send_failure()
            path = (
                "/tick"
                if envelope.ch == Channel.TICK.value
                else "/dom"
                if envelope.ch == Channel.DOM.value
                else "/envelope"
            )
            self._log(
                f"[BRIDGE_SENDER] SEND_FAIL ch={envelope.ch} seq={envelope.seq} "
                f"url={client.base_url}{path} {exc}"
            )
            return
        if envelope.ch == Channel.TICK.value:
            self.metrics.record_tick_sent()
            self._log(
                f"[BRIDGE_SENDER] sent ch=tick seq={envelope.seq} "
                f"sent_at={envelope.sent_at:.6f}"
            )
        elif envelope.ch == Channel.DOM.value:
            self.metrics.record_dom_sent()
            self._log(
                f"[BRIDGE_SENDER] sent ch=dom seq={envelope.seq} "
                f"sent_at={envelope.sent_at:.6f}"
            )

    async def _heartbeat(self, client: BridgeHttpClient) -> None:
        try:
            await client.post_heartbeat(
                tick_sent=self.metrics.tick_sent,
                dom_sent=self.metrics.dom_sent,
            )
            self.metrics.record_heartbeat(ok=True)
        except Exception as exc:  # noqa: BLE001
            self.metrics.heartbeat_ok = False
            self._log(
                f"[BRIDGE_SENDER] HEARTBEAT_FAIL url={client.base_url}/heartbeat {exc}"
            )

    async def _refresh_status(
        self,
        client: BridgeHttpClient,
        *,
        clear: bool = True,
    ) -> None:
        try:
            remote = await client.get_metrics()
            self.metrics.merge_remote(remote)
            # Successful GET /metrics means the link is up. Do not adopt the
            # receiver's connected/heartbeat_ok flags (those stay false until
            # the receiver has seen POSTs).
            self.metrics.touch_activity()
            self.metrics.connected = True
            if self.metrics.last_hb_at is not None:
                age = float(self.clock()) - float(self.metrics.last_hb_at)
                self.metrics.heartbeat_ok = age <= 5.0
        except Exception as exc:  # noqa: BLE001
            self.metrics.connected = False
            self.metrics.heartbeat_ok = False
            self._log(f"[BRIDGE_SENDER] METRICS_FAIL url={client.base_url}/metrics {exc}")
        render_bridge_status(self.metrics, self.log_stream, clear=clear)

    def _log(self, message: str) -> None:
        # Keep runtime logs after status board (no clear).
        self.log_stream.write(message + "\n")
        self.log_stream.flush()
