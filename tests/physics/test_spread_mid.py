"""Tests for spread and mid-price calculators."""

from __future__ import annotations

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.physics.mid_price import compute_mid_price
from hotirjam_ai5.physics.spread import compute_spread


def _tick(*, bid: float = 100.0, ask: float = 100.25, last: float = 100.0) -> LiveTick:
    return LiveTick(
        timestamp=1_700_000_000.0,
        symbol="MNQ",
        last_price=last,
        bid=bid,
        ask=ask,
        volume=1.0,
    )


def test_compute_spread() -> None:
    assert compute_spread(_tick(bid=20100.0, ask=20100.25)) == 0.25


def test_compute_mid_price() -> None:
    assert compute_mid_price(_tick(bid=100.0, ask=101.0)) == 100.5
    assert compute_mid_price(_tick(bid=20100.0, ask=20100.5)) == 20100.25
