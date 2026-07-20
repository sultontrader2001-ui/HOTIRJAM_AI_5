"""Tests for physics wiring in the dashboard controller."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.live_data.tick import LiveTick


def _tick(*, price: float, timestamp: float) -> LiveTick:
    return LiveTick(
        timestamp=timestamp,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price + 0.25,
        volume=1.0,
    )


def test_controller_updates_physics_from_live_ticks() -> None:
    controller = DashboardController()
    controller.start()
    controller.on_tick(_tick(price=100.0, timestamp=1.0))
    state = controller.snapshot()
    assert state.physics.spread == 0.5
    assert state.physics.mid_price == 100.0
    assert state.physics.tick_velocity is None

    controller.on_tick(_tick(price=102.0, timestamp=2.0))
    state = controller.snapshot()
    assert state.physics.tick_velocity == pytest.approx(2.0)

    controller.on_tick(_tick(price=105.0, timestamp=3.0))
    state = controller.snapshot()
    assert state.physics.tick_velocity == pytest.approx(3.0)
    assert state.physics.tick_acceleration == pytest.approx(1.0)
