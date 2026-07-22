"""Bridge Receiver runtime — accept envelopes locally, write journals (no network)."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from hotirjam_bridge.contracts import (
    DOM_FILENAME,
    TICK_FILENAME,
    Channel,
    Envelope,
)
from hotirjam_bridge.metrics import BridgeMetrics
from hotirjam_bridge.receiver.dedupe import SeqDedupe
from hotirjam_bridge.receiver.validate_dom import DomValidationError, validate_nt03_dom
from hotirjam_bridge.receiver.validate_envelope import (
    EnvelopeValidationError,
    parse_and_validate_envelope_line,
)
from hotirjam_bridge.receiver.writer import NdjsonJournalWriter
from hotirjam_bridge.sender.tail import NdjsonTail
from hotirjam_bridge.sender.validate_tick import TickValidationError, validate_nt01_tick


@dataclass
class ReceiverRuntimeStats:
    accepted_tick: int = 0
    accepted_dom: int = 0
    duplicates: int = 0
    malformed: int = 0
    hb_ctrl: int = 0
    last_tick_seq: int | None = None
    last_dom_seq: int | None = None


@dataclass
class EnvelopeReceiverRuntime:
    """Unwrap envelopes and write NT01/NT03 journals."""

    out_dir: Path
    symbol: str = "MNQ"
    flush_each_line: bool = True
    dedupe_window: int = 10_000
    poll_interval: float = 0.05
    max_messages: int | None = None
    log_stream: TextIO = field(default_factory=lambda: sys.stdout)
    sleep: Callable[[float], None] = field(default_factory=lambda: time.sleep)
    metrics: BridgeMetrics | None = None

    def __post_init__(self) -> None:
        self.out_dir = Path(self.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._tick_writer = NdjsonJournalWriter(
            self.out_dir / TICK_FILENAME,
            flush_each_line=self.flush_each_line,
        )
        self._dom_writer = NdjsonJournalWriter(
            self.out_dir / DOM_FILENAME,
            flush_each_line=self.flush_each_line,
        )
        self._dedupe = SeqDedupe(self.dedupe_window)
        self._stop = False
        self._processed = 0
        self.stats = ReceiverRuntimeStats()
        self.accepted_seq_tick: list[int] = []
        self.accepted_seq_dom: list[int] = []

    @property
    def tick_path(self) -> Path:
        return self._tick_writer.path

    @property
    def dom_path(self) -> Path:
        return self._dom_writer.path

    def request_stop(self) -> None:
        self._stop = True

    def accept(self, envelope: Envelope) -> bool:
        """Accept one envelope. Returns True if a journal line was written."""
        if self._stop:
            return False

        if envelope.ch in {Channel.HB.value, Channel.CTRL.value}:
            self.stats.hb_ctrl += 1
            self._processed += 1
            if self.metrics is not None:
                self.metrics.record_heartbeat(ok=True)
            self._log(
                f"[BRIDGE_RECEIVER] skip ch={envelope.ch} seq={envelope.seq} "
                f"(non-journal)"
            )
            return False

        try:
            if envelope.ch == Channel.TICK.value:
                validate_nt01_tick(envelope.payload, expected_symbol=self.symbol)
            elif envelope.ch == Channel.DOM.value:
                validate_nt03_dom(envelope.payload, expected_symbol=self.symbol)
            else:
                raise EnvelopeValidationError(f"unsupported ch for write: {envelope.ch}")
        except (TickValidationError, DomValidationError, EnvelopeValidationError) as exc:
            self.stats.malformed += 1
            self._processed += 1
            if self.metrics is not None:
                self.metrics.record_malformed()
            self._log(f"[BRIDGE_RECEIVER] REJECT {exc}")
            return False

        key = (envelope.ch, int(envelope.seq))
        if key in self._dedupe:
            self.stats.duplicates += 1
            self._processed += 1
            if self.metrics is not None:
                self.metrics.record_duplicate()
            self._log(
                f"[BRIDGE_RECEIVER] DUPLICATE ch={envelope.ch} seq={envelope.seq}"
            )
            return False

        try:
            if envelope.ch == Channel.TICK.value:
                digest = self._tick_writer.append_payload(envelope.payload)
                self.stats.accepted_tick += 1
                self.stats.last_tick_seq = envelope.seq
                self.accepted_seq_tick.append(envelope.seq)
                channel_file = TICK_FILENAME
                if self.metrics is not None:
                    self.metrics.record_tick_received(envelope.seq, envelope.sent_at)
            else:
                digest = self._dom_writer.append_payload(envelope.payload)
                self.stats.accepted_dom += 1
                self.stats.last_dom_seq = envelope.seq
                self.accepted_seq_dom.append(envelope.seq)
                channel_file = DOM_FILENAME
                if self.metrics is not None:
                    self.metrics.record_dom_received(envelope.seq, envelope.sent_at)
        except ValueError as exc:
            self.stats.malformed += 1
            self._processed += 1
            if self.metrics is not None:
                self.metrics.record_malformed()
            self._log(f"[BRIDGE_RECEIVER] INTEGRITY_FAIL {exc}")
            return False

        # Record dedupe only after a successful verified write.
        self._dedupe.seen_before(envelope.ch, envelope.seq)

        self._processed += 1
        self._log(
            f"[BRIDGE_RECEIVER] write ch={envelope.ch} seq={envelope.seq} "
            f"file={channel_file} sha256={digest} "
            f"sent_at={envelope.sent_at:.6f} "
            f"envelope={json.dumps({'v': envelope.v, 'ch': envelope.ch, 'seq': envelope.seq, 'src': envelope.src}, separators=(',', ':'))}"
        )
        return True

    def accept_envelope_line(self, line: str) -> bool:
        """Parse one envelope NDJSON line and accept it."""
        try:
            envelope = parse_and_validate_envelope_line(line)
        except EnvelopeValidationError as exc:
            self.stats.malformed += 1
            self._processed += 1
            if self.metrics is not None:
                self.metrics.record_malformed()
            self._log(f"[BRIDGE_RECEIVER] MALFORMED_ENVELOPE {exc}")
            return False
        return self.accept(envelope)

    def run_inbox(
        self,
        inbox_path: Path,
        *,
        start_at_eof: bool = True,
    ) -> ReceiverRuntimeStats:
        """Tail a local envelope NDJSON inbox (Sender stand-in, no network)."""
        inbox_path = Path(inbox_path)
        self._log(
            f"[BRIDGE_RECEIVER] start out_dir={self.out_dir} "
            f"inbox={inbox_path} from_eof={start_at_eof} "
            f"symbol={self.symbol} network=OFF"
        )
        tail = NdjsonTail(inbox_path, start_at_eof=start_at_eof)
        try:
            while not self._stop:
                if self.max_messages is not None and self._processed >= self.max_messages:
                    break
                for line in tail.poll():
                    if self._stop:
                        break
                    self.accept_envelope_line(line)
                    if (
                        self.max_messages is not None
                        and self._processed >= self.max_messages
                    ):
                        break
                if self._stop:
                    break
                if self.max_messages is not None and self._processed >= self.max_messages:
                    break
                self.sleep(self.poll_interval)
        finally:
            self._log(
                f"[BRIDGE_RECEIVER] stop ticks={self.stats.accepted_tick} "
                f"dom={self.stats.accepted_dom} duplicates={self.stats.duplicates} "
                f"malformed={self.stats.malformed} "
                f"last_tick_seq={self.stats.last_tick_seq} "
                f"last_dom_seq={self.stats.last_dom_seq}"
            )
        return self.stats

    def _log(self, message: str) -> None:
        self.log_stream.write(message + "\n")
        self.log_stream.flush()
