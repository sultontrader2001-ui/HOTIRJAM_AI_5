"""Bounded ring-buffer Market Memory store (Sprint 41).

Append-only. Passive Decision never writes here — adapters only.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence

from hotirjam_ai5.memory.memory_snapshot import MemoryDiagnostics, MemorySnapshot
from hotirjam_ai5.memory.memory_types import MemoryItem, MemorySource

DEFAULT_MEMORY_CAPACITY = 2048


class MarketMemoryStore:
    """Bounded ring buffer of immutable MemoryItem records.

    When capacity is exceeded, the oldest records are dropped automatically.
    Records are never modified in place.
    """

    def __init__(self, *, capacity: int = DEFAULT_MEMORY_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._items: deque[MemoryItem] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        return len(self._items)

    def append(self, item: MemoryItem) -> None:
        """Append one immutable record. Oldest drops when full."""
        if not isinstance(item, MemoryItem):
            raise TypeError("only MemoryItem may be appended")
        self._items.append(item)

    def extend(self, items: Iterable[MemoryItem]) -> None:
        """Append many records in order."""
        for item in items:
            self.append(item)

    def clear(self) -> None:
        """Drop all records (e.g. feed disconnect hard reset)."""
        self._items.clear()

    def items(self) -> Sequence[MemoryItem]:
        """Return a tuple copy — callers cannot mutate the store."""
        return tuple(self._items)

    def diagnostics(self) -> MemoryDiagnostics:
        """Memory Size, Records by Source, Oldest/Newest Timestamp."""
        counts = {source: 0 for source in MemorySource}
        oldest: float | None = None
        newest: float | None = None
        for item in self._items:
            counts[item.source] += 1
            if oldest is None or item.timestamp < oldest:
                oldest = item.timestamp
            if newest is None or item.timestamp > newest:
                newest = item.timestamp
        return MemoryDiagnostics(
            memory_size=len(self._items),
            records_by_source=counts,
            oldest_timestamp=oldest,
            newest_timestamp=newest,
        )

    def snapshot(self) -> MemorySnapshot:
        """Immutable diagnostics snapshot of current buffer contents."""
        items = tuple(self._items)
        return MemorySnapshot(items=items, diagnostics=self.diagnostics())
