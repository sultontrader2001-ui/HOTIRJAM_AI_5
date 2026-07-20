"""Physics engine — updates measurements from each live tick."""

from __future__ import annotations

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.physics.mid_price import compute_mid_price
from hotirjam_ai5.physics.spread import compute_spread
from hotirjam_ai5.physics.tick_acceleration import TickAccelerationTracker
from hotirjam_ai5.physics.tick_velocity import TickVelocityTracker


class PhysicsEngine:
    """Stateful live physics layer driven only by validated ticks."""

    def __init__(self) -> None:
        self._velocity = TickVelocityTracker()
        self._acceleration = TickAccelerationTracker()
        self._latest = PhysicsSnapshot()

    def on_tick(self, tick: LiveTick) -> PhysicsSnapshot:
        """Update measurements from one live tick and return the snapshot."""
        spread = compute_spread(tick)
        mid = compute_mid_price(tick)
        velocity_sample = self._velocity.update(
            price=tick.last_price,
            timestamp=tick.timestamp,
        )
        tick_velocity = self._latest.tick_velocity
        tick_acceleration = self._latest.tick_acceleration
        if velocity_sample is not None:
            tick_velocity = velocity_sample.velocity
            accel_sample = self._acceleration.update(velocity_sample)
            if accel_sample is not None:
                tick_acceleration = accel_sample.acceleration

        self._latest = PhysicsSnapshot(
            spread=spread,
            mid_price=mid,
            tick_velocity=tick_velocity,
            tick_acceleration=tick_acceleration,
            tick_count=self._latest.tick_count + 1,
        )
        return self._latest

    def snapshot(self) -> PhysicsSnapshot:
        """Return the latest physics snapshot without mutating state."""
        return self._latest

    def reset(self) -> None:
        """Clear all measurement state."""
        self._velocity.reset()
        self._acceleration.reset()
        self._latest = PhysicsSnapshot()
