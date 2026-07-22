"""DisplayAdapter contract — fixed-viewport paint only (H-7.2B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from hotirjam_ai5.dashboard.frame_buffer import FrameBuffer


@dataclass(frozen=True, slots=True)
class Viewport:
    """Fixed rectangular paint region."""

    rows: int
    cols: int


class DisplayAdapter(Protocol):
    """How to paint a FrameBuffer. Never appends. Never composes UI."""

    def prepare(self, viewport: Viewport) -> None:
        """Reserve viewport (cursor hide / origin). Full clear is facade-owned."""

    def paint(
        self,
        frame: FrameBuffer,
        previous: FrameBuffer | None,
        viewport: Viewport,
    ) -> None:
        """Replace viewport contents in a single pass. No stream-append."""

    def resize(self, viewport: Viewport) -> None:
        """Geometry changed — next paint must be full, not cross-geometry diff."""

    def shutdown(self, viewport: Viewport) -> None:
        """Restore terminal usability after the display session."""
