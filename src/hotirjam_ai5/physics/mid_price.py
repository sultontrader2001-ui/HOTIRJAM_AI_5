"""Mid-price measurement: (bid + ask) / 2."""

from __future__ import annotations

from hotirjam_ai5.live_data.tick import LiveTick


def compute_mid_price(tick: LiveTick) -> float:
    """Return the mid price for one tick."""
    return (tick.bid + tick.ask) / 2.0
