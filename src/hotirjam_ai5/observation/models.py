"""Observation cycle record — one completed architecture observation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObservationCycle:
    """Fields recorded for every completed observation cycle (H-8.0)."""

    cycle_id: int
    time: float
    objective: str
    initiative: str
    response: str
    continuation: str
    break_capability: str
    confidence: str
    market_state: str
    evidence: str
    no_trade_reason: str
    decision: str
    symbol: str = "N/A"
    price: str = "N/A"
