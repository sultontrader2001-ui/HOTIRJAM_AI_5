"""Bridge Sender tick runtime — tail, validate, envelope, log (no network)."""

from __future__ import annotations

import json
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from hotirjam_bridge.contracts import DEFAULT_SENDER_ID, Envelope
from hotirjam_bridge.sender.envelope import wrap_tick
from hotirjam_bridge.sender.tail import NdjsonTail
from hotirjam_bridge.sender.validate_tick import (
    TickValidationError,
    parse_tick_json,
    validate_nt01_tick,
)


@dataclass
class SenderRuntimeStats:
    lines_read: int = 0
    ticks_accepted: int = 0
    malformed: int = 0
    last_seq: int = 0


@dataclass
class TickSenderRuntime:
    """M1.2: observe NT01 ticks locally; do not transmit."""

    tick_file: Path
    symbol: str = "MNQ"
    sender_id: str = DEFAULT_SENDER_ID
    session_id: str | None = None
    poll_interval: float = 0.05
    start_at_eof: bool = True
    max_ticks: int | None = None
    log_stream: TextIO = field(default_factory=lambda: sys.stdout)
    clock: Callable[[], float] = field(default_factory=lambda: time.time)
    sleep: Callable[[float], None] = field(default_factory=lambda: time.sleep)
    on_envelope: Callable[[Envelope], None] | None = None

    def __post_init__(self) -> None:
        self.tick_file = Path(self.tick_file)
        self.sender_id = str(self.sender_id or DEFAULT_SENDER_ID)
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        self._tail = NdjsonTail(self.tick_file, start_at_eof=self.start_at_eof)
        self._seq = 0
        self._stop = False
        self.stats = SenderRuntimeStats()
        self.envelopes: list[Envelope] = []

    @property
    def offset(self) -> int:
        return self._tail.offset

    def request_stop(self) -> None:
        """Signal clean shutdown (Ctrl+C / tests)."""
        self._stop = True

    def run(self) -> SenderRuntimeStats:
        self._log(
            f"[BRIDGE_SENDER] start file={self.tick_file} "
            f"sender_id={self.sender_id} session_id={self.session_id} "
            f"symbol={self.symbol} from_eof={self.start_at_eof} "
            f"poll={self.poll_interval} network=OFF"
        )
        try:
            while not self._stop:
                if self.max_ticks is not None and self.stats.ticks_accepted >= self.max_ticks:
                    break
                self.poll_once()
                if self.max_ticks is not None and self.stats.ticks_accepted >= self.max_ticks:
                    break
                if self._stop:
                    break
                self.sleep(self.poll_interval)
        finally:
            self._log(
                f"[BRIDGE_SENDER] stop accepted={self.stats.ticks_accepted} "
                f"malformed={self.stats.malformed} last_seq={self.stats.last_seq} "
                f"offset={self._tail.offset}"
            )
        return self.stats

    def poll_once(self) -> list[Envelope]:
        """Read available new lines once; return accepted envelopes."""
        accepted: list[Envelope] = []
        for line in self._tail.poll():
            if self._stop:
                break
            self.stats.lines_read += 1
            try:
                payload = validate_nt01_tick(
                    parse_tick_json(line),
                    expected_symbol=self.symbol,
                )
            except TickValidationError as exc:
                self.stats.malformed += 1
                self._log(f"[BRIDGE_SENDER] MALFORMED {exc}")
                continue

            self._seq += 1
            envelope = wrap_tick(
                payload,
                seq=self._seq,
                sender_id=self.sender_id,
                session_id=str(self.session_id),
                clock=self.clock,
            )
            self.stats.ticks_accepted += 1
            self.stats.last_seq = self._seq
            self.envelopes.append(envelope)
            accepted.append(envelope)
            self._log_envelope(envelope)
            if self.on_envelope is not None:
                self.on_envelope(envelope)
            if self.max_ticks is not None and self.stats.ticks_accepted >= self.max_ticks:
                break
        return accepted

    def _log_envelope(self, envelope: Envelope) -> None:
        payload = envelope.payload
        self._log(
            "[BRIDGE_SENDER] "
            f"seq={envelope.seq} ch={envelope.ch} "
            f"symbol={payload.get('symbol')} "
            f"last={payload.get('last_price')} "
            f"bid={payload.get('bid')} ask={payload.get('ask')} "
            f"vol={payload.get('volume')} "
            f"sent_at={envelope.sent_at:.6f} "
            f"payload_ts={payload.get('timestamp')} "
            f"envelope={json.dumps(envelope.as_dict(), separators=(',', ':'), sort_keys=True)}"
        )

    def _log(self, message: str) -> None:
        self.log_stream.write(message + "\n")
        self.log_stream.flush()
