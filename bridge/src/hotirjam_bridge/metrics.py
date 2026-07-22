"""Bridge transport metrics + terminal status board (M1.4)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class BridgeMetrics:
    """Shared counters for Sender / Receiver status display."""

    tick_sent: int = 0
    tick_received: int = 0
    dom_sent: int = 0
    dom_received: int = 0
    dropped: int = 0
    duplicate: int = 0
    malformed: int = 0
    send_failures: int = 0
    latency_sum_ms: float = 0.0
    latency_count: int = 0
    last_hb_at: float | None = None
    last_activity_at: float | None = None
    connected: bool = False
    heartbeat_ok: bool = False
    _next_tick_seq: int | None = None
    _next_dom_seq: int | None = None
    _clock: Callable[[], float] = field(default=time.time, repr=False)

    @property
    def latency_avg_ms(self) -> float | None:
        if self.latency_count <= 0:
            return None
        return self.latency_sum_ms / self.latency_count

    def touch_activity(self) -> None:
        self.last_activity_at = float(self._clock())
        self.connected = True

    def record_heartbeat(self, *, ok: bool = True) -> None:
        self.last_hb_at = float(self._clock())
        self.heartbeat_ok = ok
        self.touch_activity()

    def record_tick_sent(self) -> None:
        self.tick_sent += 1
        self.touch_activity()

    def record_dom_sent(self) -> None:
        self.dom_sent += 1
        self.touch_activity()

    def record_send_failure(self) -> None:
        self.send_failures += 1
        self.dropped += 1

    def record_tick_received(self, seq: int, sent_at: float) -> None:
        self._record_seq_gap("tick", seq)
        self.tick_received += 1
        self._record_latency(sent_at)
        self.touch_activity()

    def record_dom_received(self, seq: int, sent_at: float) -> None:
        self._record_seq_gap("dom", seq)
        self.dom_received += 1
        self._record_latency(sent_at)
        self.touch_activity()

    def record_duplicate(self) -> None:
        self.duplicate += 1
        self.touch_activity()

    def record_malformed(self) -> None:
        self.malformed += 1
        self.dropped += 1

    def refresh_connected(self, *, stale_after: float = 5.0) -> None:
        now = float(self._clock())
        if self.last_activity_at is None:
            self.connected = False
            self.heartbeat_ok = False
            return
        self.connected = (now - self.last_activity_at) <= stale_after
        if self.last_hb_at is None:
            self.heartbeat_ok = self.connected
        else:
            self.heartbeat_ok = (now - self.last_hb_at) <= stale_after

    def _record_latency(self, sent_at: float) -> None:
        lag_ms = max(0.0, (float(self._clock()) - float(sent_at)) * 1000.0)
        self.latency_sum_ms += lag_ms
        self.latency_count += 1

    def _record_seq_gap(self, channel: str, seq: int) -> None:
        seq = int(seq)
        if channel == "tick":
            expected = self._next_tick_seq
            if expected is None:
                self._next_tick_seq = seq + 1
                return
            if seq > expected:
                self.dropped += seq - expected
                self._next_tick_seq = seq + 1
            elif seq == expected:
                self._next_tick_seq = seq + 1
            # seq < expected: duplicate/reorder — duplicate counter handles dupes
        else:
            expected = self._next_dom_seq
            if expected is None:
                self._next_dom_seq = seq + 1
                return
            if seq > expected:
                self.dropped += seq - expected
                self._next_dom_seq = seq + 1
            elif seq == expected:
                self._next_dom_seq = seq + 1

    def as_dict(self) -> dict[str, object]:
        self.refresh_connected()
        return {
            "connected": self.connected,
            "tick_sent": self.tick_sent,
            "tick_received": self.tick_received,
            "dom_sent": self.dom_sent,
            "dom_received": self.dom_received,
            "dropped": self.dropped,
            "duplicate": self.duplicate,
            "malformed": self.malformed,
            "send_failures": self.send_failures,
            "latency_avg_ms": self.latency_avg_ms,
            "heartbeat_ok": self.heartbeat_ok,
            "last_hb_at": self.last_hb_at,
            "last_activity_at": self.last_activity_at,
        }

    def merge_remote(self, remote: dict[str, object]) -> None:
        """Fill receive-side fields from Receiver GET /metrics."""
        if "tick_received" in remote:
            self.tick_received = int(remote["tick_received"])  # type: ignore[arg-type]
        if "dom_received" in remote:
            self.dom_received = int(remote["dom_received"])  # type: ignore[arg-type]
        if "dropped" in remote:
            # Prefer max so sender-local send_failures are not erased incorrectly;
            # remote dropped is authoritative for gaps.
            self.dropped = max(self.dropped, int(remote["dropped"]))  # type: ignore[arg-type]
        if "duplicate" in remote:
            self.duplicate = int(remote["duplicate"])  # type: ignore[arg-type]
        if "latency_avg_ms" in remote and remote["latency_avg_ms"] is not None:
            # Display remote avg when present
            avg = float(remote["latency_avg_ms"])  # type: ignore[arg-type]
            self.latency_sum_ms = avg
            self.latency_count = 1
        if "heartbeat_ok" in remote:
            self.heartbeat_ok = bool(remote["heartbeat_ok"])
        if "connected" in remote:
            self.connected = bool(remote["connected"])


def format_bridge_status(metrics: BridgeMetrics) -> str:
    """Terminal Bridge Status board (always visible layout)."""
    metrics.refresh_connected()
    latency = metrics.latency_avg_ms
    latency_s = f"{latency:.2f} ms" if latency is not None else "n/a"
    connected = "YES" if metrics.connected else "NO"
    hb = "OK" if metrics.heartbeat_ok else "FAIL"
    return "\n".join(
        [
            "Bridge Status",
            f"Connected: {connected}",
            f"Tick Sent: {metrics.tick_sent}",
            f"Tick Received: {metrics.tick_received}",
            f"Dropped: {metrics.dropped}",
            f"Duplicate: {metrics.duplicate}",
            f"Latency Avg: {latency_s}",
            f"Heartbeat: {hb}",
        ]
    )


def render_bridge_status(
    metrics: BridgeMetrics,
    stream: TextIO,
    *,
    clear: bool = True,
) -> None:
    """Write status board to terminal (optional ANSI clear)."""
    board = format_bridge_status(metrics)
    if clear:
        stream.write("\033[H\033[2J")
    stream.write(board + "\n")
    stream.flush()
