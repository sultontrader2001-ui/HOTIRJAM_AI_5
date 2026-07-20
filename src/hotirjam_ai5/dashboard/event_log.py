"""Bounded in-memory event log for the dashboard LOG section."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class EventLog:
    """Stores the most recent dashboard events (newest last)."""

    capacity: int = 5
    _events: deque[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._events = deque(maxlen=self.capacity)

    def append(self, message: str) -> None:
        """Record one event line."""
        text = message.strip()
        if not text:
            raise ValueError("event message must be non-empty")
        self._events.append(text)

    def clear(self) -> None:
        """Remove all events."""
        self._events.clear()

    def latest(self) -> tuple[str, ...]:
        """Return events from oldest to newest."""
        return tuple(self._events)

    def __len__(self) -> int:
        return len(self._events)
