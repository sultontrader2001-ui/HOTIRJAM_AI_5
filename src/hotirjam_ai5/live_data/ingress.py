"""Live tick ingress: poll NT01 NDJSON and emit validated LiveTick values."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_data.ndjson_tail import NdjsonFileTail
from hotirjam_ai5.live_data.paths import default_tick_path
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_data.tick_parser import TickParseError, TickParser


class LiveTickIngress:
    """Reads live NT01 ticks from disk. Invalid lines are skipped, not invented."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        parser: TickParser | None = None,
        expected_symbol: str = "MNQ",
    ) -> None:
        self.path = Path(path) if path is not None else default_tick_path()
        self._parser = parser or TickParser(expected_symbol=expected_symbol)
        self._tail = NdjsonFileTail(self.path)
        self._accepted = 0
        self._skipped = 0

    @property
    def accepted_count(self) -> int:
        return self._accepted

    @property
    def skipped_count(self) -> int:
        return self._skipped

    def poll(self) -> tuple[LiveTick, ...]:
        """Parse newly appended lines into LiveTick objects."""
        ticks: list[LiveTick] = []
        for line in self._tail.poll():
            try:
                tick = self._parser.parse_line(line)
            except TickParseError:
                self._skipped += 1
                continue
            self._accepted += 1
            ticks.append(tick)
        return tuple(ticks)
