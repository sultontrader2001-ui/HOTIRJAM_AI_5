"""Structured logging helpers for HOTIRJAM Gateway."""

from __future__ import annotations

import logging
import sys
from typing import TextIO


_CONFIGURED = False
LOGGER_NAME = "hotirjam_gateway"


class GatewayLogFormatter(logging.Formatter):
    """Compact structured-ish text format for ops logs."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras: list[str] = []
        for key in (
            "gateway_event",
            "from_state",
            "to_state",
            "reason",
            "health",
            "session_id",
            "sender_id",
            "hb_ok",
            "hb_age_s",
            "connection_id",
            "host",
            "port",
            "remote_addr",
            "messages_received",
            "bytes_received",
        ):
            value = getattr(record, key, None)
            if value is not None:
                extras.append(f"{key}={value}")
        if not extras:
            return base
        return f"{base} | {' '.join(extras)}"


def setup_logging(
    *,
    level: int = logging.INFO,
    stream: TextIO | None = None,
    force: bool = False,
) -> logging.Logger:
    """Configure the ``hotirjam_gateway`` logger once (idempotent unless force)."""
    global _CONFIGURED
    logger = logging.getLogger(LOGGER_NAME)
    if _CONFIGURED and not force:
        return logger

    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(
        GatewayLogFormatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under ``hotirjam_gateway``."""
    setup_logging()
    if not name or name == LOGGER_NAME:
        return logging.getLogger(LOGGER_NAME)
    if name.startswith(LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
