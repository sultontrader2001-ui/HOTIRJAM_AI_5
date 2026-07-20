"""Validated live tick from NinjaTrader."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LiveTick:
    """One live trade tick. All prices must be real values from the feed."""

    timestamp: float
    symbol: str
    last_price: float
    bid: float
    ask: float
    volume: float

    @property
    def spread(self) -> float:
        return self.ask - self.bid
