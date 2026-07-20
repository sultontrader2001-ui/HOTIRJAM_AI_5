"""Temporary ingress diagnostics (stderr). Remove after live feed is verified."""

from __future__ import annotations

import os
import sys
from typing import TextIO


def ingress_debug_enabled() -> bool:
    """Diagnostics default OFF; set HOTIRJAM_INGRESS_DEBUG=1 to enable."""
    raw = os.environ.get("HOTIRJAM_INGRESS_DEBUG", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class IngressDiagnostics:
    """Writes temporary tick-ingestion diagnostics to stderr."""

    def __init__(self, *, enabled: bool | None = None, stream: TextIO | None = None) -> None:
        self.enabled = ingress_debug_enabled() if enabled is None else enabled
        self._stream = stream or sys.stderr

    def log(self, message: str) -> None:
        if not self.enabled:
            return
        self._stream.write(f"[INGRESS] {message}\n")
        self._stream.flush()
