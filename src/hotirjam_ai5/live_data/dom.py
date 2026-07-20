"""Validated live DOM snapshot from NinjaTrader NT04."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomSnapshot:
    """One live DOM snapshot. Sizes come from NT04 — never invented."""

    timestamp_utc: str
    instrument: str
    depth_levels: int
    best_bid_size: int | None
    best_ask_size: int | None
    total_bid_size: int
    total_ask_size: int
    status: str
