"""Live DOM ingress: poll NT04 NDJSON and emit validated DomSnapshot values."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_data.diagnostics import IngressDiagnostics
from hotirjam_ai5.live_data.dom import DomSnapshot
from hotirjam_ai5.live_data.dom_parser import DomParseError, DomParser
from hotirjam_ai5.live_data.ndjson_tail import NdjsonFileTail
from hotirjam_ai5.live_data.paths import default_dom_path


class LiveDomIngress:
    """Reads live NT04 DOM snapshots from disk. Invalid lines are skipped."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        parser: DomParser | None = None,
        expected_symbol: str = "MNQ",
        diagnostics: IngressDiagnostics | None = None,
    ) -> None:
        resolved = Path(path) if path is not None else default_dom_path()
        resolved = Path(resolved).expanduser()
        try:
            resolved = resolved.resolve()
        except OSError:
            resolved = resolved.absolute()

        self._diagnostics = diagnostics or IngressDiagnostics()
        self.path = resolved
        self._parser = parser or DomParser(expected_symbol=expected_symbol)
        self._tail = NdjsonFileTail(self.path, diagnostics=self._diagnostics)
        self._accepted = 0
        self._skipped = 0
        self._proven_consumed_offset: int | None = None
        self._diagnostics.log(
            f"DOM ingress ready path={self.path} exists={self.path.exists()} "
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
        return self._proven_consumed_offset

    def poll(self) -> tuple[DomSnapshot, ...]:
        """Parse newly appended lines into DomSnapshot objects."""
        snapshots: list[DomSnapshot] = []
        raw_lines = self._tail.poll()
        if raw_lines:
            self._proven_consumed_offset = self._tail.offset
        for line in raw_lines:
            try:
                snapshot = self._parser.parse_line(line)
            except DomParseError as exc:
                self._skipped += 1
                self._diagnostics.log(f"DOM parse failure: {exc} | line={line!r}")
                continue
            self._accepted += 1
            snapshots.append(snapshot)
            self._diagnostics.log(
                f"DOM parse success / snapshot emitted "
                f"#{self._accepted} instrument={snapshot.instrument} "
                f"bid_total={snapshot.total_bid_size} ask_total={snapshot.total_ask_size} "
                f"status={snapshot.status}"
            )
        return tuple(snapshots)

    def apply_safe_storage_retention(self, *, max_bytes: int) -> bool:
        """Storage-only: drop proven-consumed prefix if file exceeds ``max_bytes``."""
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
