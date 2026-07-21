"""Memory diagnostics snapshot (Sprint 41) — not rendered on dashboard yet."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.memory.memory_types import MemoryItem, MemorySource


@dataclass(frozen=True, slots=True)
class MemoryDiagnostics:
    """Passive diagnostics for the Market Memory store."""

    memory_size: int
    records_by_source: dict[MemorySource, int]
    oldest_timestamp: float | None
    newest_timestamp: float | None


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    """Immutable view of store contents for diagnostics / future readers.

    Trade Decision must not consume this in Sprint 41.
    """

    items: tuple[MemoryItem, ...]
    diagnostics: MemoryDiagnostics
