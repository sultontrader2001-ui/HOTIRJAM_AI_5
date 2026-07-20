"""Spread measurement: ask − bid."""

from __future__ import annotations

from hotirjam_ai5.live_data.tick import LiveTick


def compute_spread(tick: LiveTick) -> float:
    """Return the bid-ask spread for one tick."""
    return tick.ask - tick.bid
