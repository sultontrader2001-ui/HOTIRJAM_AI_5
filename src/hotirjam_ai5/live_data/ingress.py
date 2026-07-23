"""Live tick ingress: poll NT01 NDJSON and emit validated LiveTick values."""

from __future__ import annotations

import sys
from pathlib import Path

from hotirjam_ai5.live_data.diagnostics import IngressDiagnostics, ingress_poll_stderr_enabled
from hotirjam_ai5.live_data.ingress_poll_snapshot import IngressPollSnapshot
from hotirjam_ai5.live_data.ndjson_tail import NdjsonFileTail
from hotirjam_ai5.live_data.paths import default_tick_path
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_data.tick_parser import TickParseError, TickParser

# Debug-only stderr prefix (H-8.1A: default OFF).
_POLL_DIAG_PREFIX = "[INGRESS_POLL]"


class LiveTickIngress:
    """Reads live NT01 ticks from disk. Invalid lines are skipped, not invented."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        parser: TickParser | None = None,
        expected_symbol: str = "MNQ",
        diagnostics: IngressDiagnostics | None = None,
    ) -> None:
        resolved = Path(path) if path is not None else default_tick_path()
        resolved = Path(resolved).expanduser()
        try:
            resolved = resolved.resolve()
        except OSError:
            resolved = resolved.absolute()

        self._diagnostics = diagnostics or IngressDiagnostics()
        self.path = resolved
        self._parser = parser or TickParser(expected_symbol=expected_symbol)
        self._tail = NdjsonFileTail(self.path, diagnostics=self._diagnostics)
        self._accepted = 0
        self._skipped = 0
        self._last_poll: IngressPollSnapshot | None = None
        # Bytes through which complete lines were returned from poll (proven consumed).
        # None until at least one non-empty poll delivers lines — never truncate on uncertainty.
        self._proven_consumed_offset: int | None = None
        self._diagnostics.log(
            f"Ingress ready path={self.path} exists={self.path.exists()} "
            f"expected_symbol={self._parser.expected_symbol}"
        )

    @property
    def accepted_count(self) -> int:
        return self._accepted

    @property
    def skipped_count(self) -> int:
        return self._skipped

    @property
    def proven_consumed_offset(self) -> int | None:
        """Byte offset through which ingress has returned complete lines, or None."""
        return self._proven_consumed_offset

    @property
    def last_poll(self) -> IngressPollSnapshot | None:
        """TEMPORARY — snapshot from the most recent ``poll()`` call."""
        return self._last_poll

    def poll(self) -> tuple[LiveTick, ...]:
        """Parse newly appended lines into LiveTick objects."""
        before_accepted = self._accepted
        before_skipped = self._skipped

        # Observation only: capture line count; same iteration/parse as before.
        raw_lines = self._tail.poll()
        tail_lines = len(raw_lines)
        if tail_lines > 0:
            # Only complete lines returned by the tail are proven consumed.
            self._proven_consumed_offset = self._tail.offset

        ticks: list[LiveTick] = []
        for line in raw_lines:
            try:
                tick = self._parser.parse_line(line)
            except TickParseError as exc:
                self._skipped += 1
                self._diagnostics.log(f"Parse failure: {exc} | line={line!r}")
                continue
            self._accepted += 1
            ticks.append(tick)
            self._diagnostics.log(
                f"Parse success / tick emitted "
                f"#{self._accepted} symbol={tick.symbol} last={tick.last_price} "
                f"bid={tick.bid} ask={tick.ask} volume={tick.volume}"
            )

        file_size: int | None
        try:
            file_size = self.path.stat().st_size
        except OSError:
            file_size = None

        snapshot = IngressPollSnapshot(
            tail_lines=tail_lines,
            accepted_count=self._accepted,
            skipped_count=self._skipped,
            accepted_delta=self._accepted - before_accepted,
            skipped_delta=self._skipped - before_skipped,
            file_offset=self._tail.offset,
            file_size=file_size,
            tail_return=getattr(self._tail, "last_return_reason", ""),
        )
        self._last_poll = snapshot
        self._emit_poll_snapshot(snapshot)
        return tuple(ticks)

    def apply_safe_storage_retention(self, *, max_bytes: int) -> bool:
        """Storage-only: drop proven-consumed prefix if file exceeds ``max_bytes``.

        Never runs inside engine evaluation. Never deletes unconsumed bytes.
        """
        try:
            from hotirjam_ai5.retention import enforce_ndjson_size_limit

            trimmed = enforce_ndjson_size_limit(
                self.path,
                max_bytes=max_bytes,
                consumed_offset=self._proven_consumed_offset,
            )
            if not trimmed:
                return False
            try:
                new_size = self.path.stat().st_size
            except OSError:
                new_size = 0
            self._tail.mark_prefix_removed(new_size=new_size)
            self._proven_consumed_offset = None
            return True
        except Exception:
            return False

    def _emit_poll_snapshot(self, snapshot: IngressPollSnapshot) -> None:
        """Optionally mirror poll snapshot to stderr (debug only; default OFF).

        IngressPollSnapshot remains canonical via ``last_poll``. Production
        operator TTY must not scroll (H-8.1A / H-7.2D).
        """
        if not ingress_poll_stderr_enabled():
            return
        offset = "NA" if snapshot.file_offset is None else str(snapshot.file_offset)
        size = "NA" if snapshot.file_size is None else str(snapshot.file_size)
        sys.stderr.write(
            f"{_POLL_DIAG_PREFIX} "
            f"gate={snapshot.gate} "
            f"tail_return={snapshot.tail_return!r} "
            f"tail_lines={snapshot.tail_lines} "
            f"accepted_count={snapshot.accepted_count} "
            f"skipped_count={snapshot.skipped_count} "
            f"accepted_delta={snapshot.accepted_delta} "
            f"skipped_delta={snapshot.skipped_delta} "
            f"file_offset={offset} "
            f"file_size={size}\n"
        )
        sys.stderr.flush()
