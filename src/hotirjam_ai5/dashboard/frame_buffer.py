"""Immutable terminal presentation frame (H-7.2B / H-7.2C)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameBuffer:
    """Terminal-agnostic frame. Owns lines only — never runtime state."""

    lines: tuple[str, ...]
    width: int
    height: int
    identity: str
    timestamp: float

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        width: int | None = None,
        height: int | None = None,
        identity: str | None = None,
        timestamp: float | None = None,
    ) -> FrameBuffer:
        lines = tuple(text.splitlines())
        content_width = max((len(line) for line in lines), default=0)
        resolved_width = content_width if width is None else max(0, width)
        resolved_height = len(lines) if height is None else max(0, height)
        stamp = time.time() if timestamp is None else timestamp
        resolved_identity = identity if identity is not None else _content_identity(lines)
        return cls(
            lines=lines,
            width=resolved_width,
            height=resolved_height,
            identity=resolved_identity,
            timestamp=stamp,
        )

    def same_content(self, other: FrameBuffer) -> bool:
        """True when painted content matches (identity may differ)."""
        return self.lines == other.lines

    def same_for_skip(self, other: FrameBuffer) -> bool:
        """Facade skip: identical identity or identical content."""
        return self.identity == other.identity or self.same_content(other)


def _content_identity(lines: tuple[str, ...]) -> str:
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]
