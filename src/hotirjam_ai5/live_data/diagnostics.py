"""Temporary ingress diagnostics (stderr). Default OFF in production."""

from __future__ import annotations

import os
import sys
from typing import TextIO


def _env_truthy(name: str) -> bool:
    raw = os.environ.get(name, "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def ingress_debug_enabled() -> bool:
    """[INGRESS] parse logs. Default OFF; set HOTIRJAM_INGRESS_DEBUG=1."""
    return _env_truthy("HOTIRJAM_INGRESS_DEBUG")


def ingress_poll_stderr_enabled() -> bool:
    """[INGRESS_POLL] stderr lines. Default OFF (H-8.1A).

    Enable with HOTIRJAM_INGRESS_POLL_STDERR=1, or HOTIRJAM_INGRESS_DEBUG=1
    (debug mode enables all ingress stderr triage).
    """
    return _env_truthy("HOTIRJAM_INGRESS_POLL_STDERR") or ingress_debug_enabled()


class IngressDiagnostics:
    """Writes temporary tick-ingestion diagnostics to stderr when enabled."""

    def __init__(self, *, enabled: bool | None = None, stream: TextIO | None = None) -> None:
        self.enabled = ingress_debug_enabled() if enabled is None else enabled
        self._stream = stream or sys.stderr

    def log(self, message: str) -> None:
        if not self.enabled:
            return
        self._stream.write(f"[INGRESS] {message}\n")
        self._stream.flush()
