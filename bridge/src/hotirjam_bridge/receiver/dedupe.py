"""Bounded (session_id, channel, seq) dedupe window for Receiver."""

from __future__ import annotations

from collections import OrderedDict


class SeqDedupe:
    """Return True if ``(session_id, ch, seq)`` was already seen."""

    def __init__(self, window: int = 10_000) -> None:
        self._window = max(1, int(window))
        self._seen: OrderedDict[tuple[str, str, int], None] = OrderedDict()

    def __contains__(self, key: tuple[str, str, int]) -> bool:
        return key in self._seen

    def seen_before(self, session_id: str, ch: str, seq: int) -> bool:
        key = (str(session_id), ch, int(seq))
        if key in self._seen:
            return True
        self._seen[key] = None
        while len(self._seen) > self._window:
            self._seen.popitem(last=False)
        return False

    def __len__(self) -> int:
        return len(self._seen)
