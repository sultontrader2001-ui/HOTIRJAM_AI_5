"""Tests for PhysicsEngine live updates."""

from __future__ import annotations

import pytest

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.physics.engine import PhysicsEngine


def _tick(*, price: float, timestamp: float, bid: float | None = None) -> LiveTick:
    bid_price = bid if bid is not None else price - 0.25
    return LiveTick(
        timestamp=timestamp,
        symbol="MNQ",
        last_price=price,
        bid=bid_price,
        ask=bid_price + 0.25,
        volume=1.0,
    )


def test_first_tick_sets_spread_and_mid_only() -> None:
    engine = PhysicsEngine()
    snap = engine.on_tick(_tick(price=20100.0, timestamp=1.0, bid=20100.0))
    assert snap.spread == 0.25
    assert snap.mid_price == 20100.125
    assert snap.tick_velocity is None
    assert snap.tick_acceleration is None
    assert snap.tick_count == 1


def test_second_tick_sets_velocity() -> None:
    engine = PhysicsEngine()
    engine.on_tick(_tick(price=100.0, timestamp=10.0, bid=100.0))
    snap = engine.on_tick(_tick(price=104.0, timestamp=12.0, bid=104.0))
    assert snap.tick_velocity == pytest.approx(2.0)
    assert snap.tick_acceleration is None
    assert snap.tick_count == 2


def test_third_tick_sets_acceleration() -> None:
    engine = PhysicsEngine()
    engine.on_tick(_tick(price=100.0, timestamp=0.0, bid=100.0))
    engine.on_tick(_tick(price=102.0, timestamp=1.0, bid=102.0))  # v=2
    snap = engine.on_tick(_tick(price=106.0, timestamp=2.0, bid=106.0))  # v=4, a=2
    assert snap.tick_velocity == pytest.approx(4.0)
    assert snap.tick_acceleration == pytest.approx(2.0)


def test_snapshot_is_latest_without_mutation() -> None:
    engine = PhysicsEngine()
    engine.on_tick(_tick(price=100.0, timestamp=1.0, bid=100.0))
    before = engine.snapshot()
    engine.on_tick(_tick(price=101.0, timestamp=2.0, bid=101.0))
    assert before.tick_count == 1
    assert engine.snapshot().tick_count == 2


def test_reset_clears_measurements() -> None:
    engine = PhysicsEngine()
    engine.on_tick(_tick(price=100.0, timestamp=1.0, bid=100.0))
    engine.on_tick(_tick(price=101.0, timestamp=2.0, bid=101.0))
    engine.reset()
    snap = engine.snapshot()
    assert snap.spread is None
    assert snap.tick_velocity is None
    assert snap.tick_count == 0
