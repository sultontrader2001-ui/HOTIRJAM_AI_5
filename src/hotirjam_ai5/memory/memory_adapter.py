"""Memory adapters — map engine snapshots to MemoryItem (Sprint 41).

Existing engines are unchanged. Trade Decision does not write to Memory;
DecisionAdapter is the only path for decision records.
"""

from __future__ import annotations

from hotirjam_ai5.liquidity.models import LiquiditySnapshot
from hotirjam_ai5.market_behavior.models import BehaviorSnapshot
from hotirjam_ai5.market_state.models import MarketState, MarketStateSnapshot
from hotirjam_ai5.memory.memory_store import MarketMemoryStore
from hotirjam_ai5.memory.memory_types import MemoryItem, MemorySource
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot

_NEUTRAL = "NEUTRAL"


def _clamp_confidence(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


class PhysicsAdapter:
    """PhysicsSnapshot → MemoryItem (no raw ticks)."""

    @staticmethod
    def to_item(physics: PhysicsSnapshot, *, timestamp: float) -> MemoryItem | None:
        velocity = physics.tick_velocity
        acceleration = physics.tick_acceleration
        if velocity is None and acceleration is None:
            return None
        if velocity is None or velocity == 0.0:
            direction = _NEUTRAL
        elif velocity > 0.0:
            direction = "UP"
        else:
            direction = "DOWN"
        strength = 0.0
        if velocity is not None:
            strength += abs(velocity)
        if acceleration is not None:
            strength += abs(acceleration)
        if velocity is not None and acceleration is not None:
            confidence = 1.0
        else:
            confidence = 0.5
        return MemoryItem(
            timestamp=timestamp,
            source=MemorySource.PHYSICS,
            direction=direction,
            strength=strength,
            confidence=confidence,
        )

    @staticmethod
    def record(
        store: MarketMemoryStore,
        physics: PhysicsSnapshot,
        *,
        timestamp: float,
    ) -> MemoryItem | None:
        item = PhysicsAdapter.to_item(physics, timestamp=timestamp)
        if item is not None:
            store.append(item)
        return item


class LiquidityAdapter:
    """LiquiditySnapshot → MemoryItem (no raw DOM)."""

    @staticmethod
    def to_item(liquidity: LiquiditySnapshot) -> MemoryItem:
        direction = str(liquidity.liquidity_shift)
        confidence = _clamp_confidence(float(liquidity.confidence))
        return MemoryItem(
            timestamp=liquidity.timestamp,
            source=MemorySource.LIQUIDITY,
            direction=direction,
            strength=confidence,
            confidence=confidence,
        )

    @staticmethod
    def record(
        store: MarketMemoryStore,
        liquidity: LiquiditySnapshot,
    ) -> MemoryItem:
        item = LiquidityAdapter.to_item(liquidity)
        store.append(item)
        return item


class StateAdapter:
    """MarketStateSnapshot → MemoryItem."""

    @staticmethod
    def to_item(state: MarketStateSnapshot) -> MemoryItem | None:
        if state.state is MarketState.UNKNOWN:
            return None
        strength_map = {
            MarketState.QUIET: 0.2,
            MarketState.NORMAL: 0.4,
            MarketState.ACTIVE: 0.7,
            MarketState.TRENDING: 0.9,
            MarketState.VOLATILE: 1.0,
        }
        strength = strength_map.get(state.state, 0.0)
        return MemoryItem(
            timestamp=state.timestamp,
            source=MemorySource.STATE,
            direction=state.direction.value,
            strength=strength,
            confidence=1.0,
        )

    @staticmethod
    def record(
        store: MarketMemoryStore,
        state: MarketStateSnapshot,
    ) -> MemoryItem | None:
        item = StateAdapter.to_item(state)
        if item is not None:
            store.append(item)
        return item


class BehaviorAdapter:
    """BehaviorSnapshot → MemoryItem."""

    @staticmethod
    def to_item(behavior: BehaviorSnapshot) -> MemoryItem | None:
        if behavior.behavior.value == "UNKNOWN":
            return None
        strength_map = {
            "STABLE": 0.5,
            "ACCELERATING": 0.9,
            "DECELERATING": 0.7,
            "BALANCED": 0.4,
            "UNSTABLE": 1.0,
        }
        strength = strength_map.get(behavior.behavior.value, 0.0)
        return MemoryItem(
            timestamp=behavior.timestamp,
            source=MemorySource.BEHAVIOR,
            direction=behavior.direction.value,
            strength=strength,
            confidence=1.0,
        )

    @staticmethod
    def record(
        store: MarketMemoryStore,
        behavior: BehaviorSnapshot,
    ) -> MemoryItem | None:
        item = BehaviorAdapter.to_item(behavior)
        if item is not None:
            store.append(item)
        return item


class DecisionAdapter:
    """TradeDecisionSnapshot → MemoryItem.

    The only allowed path for decision records. TradeDecisionEngine never
    calls MarketMemoryStore.append itself.
    """

    @staticmethod
    def to_item(decision: TradeDecisionSnapshot) -> MemoryItem:
        if decision.decision is TradeDecision.BUY_INTERNAL:
            direction = "BUY"
            strength = float(decision.buy_score)
            confidence = _clamp_confidence(decision.buy_confidence / 100.0)
        elif decision.decision is TradeDecision.SELL_INTERNAL:
            direction = "SELL"
            strength = float(decision.sell_score)
            confidence = _clamp_confidence(decision.sell_confidence / 100.0)
        else:
            direction = "NO_TRADE"
            strength = float(max(decision.buy_score, decision.sell_score))
            confidence = _clamp_confidence(
                max(decision.buy_confidence, decision.sell_confidence) / 100.0
            )
        return MemoryItem(
            timestamp=decision.timestamp,
            source=MemorySource.DECISION,
            direction=direction,
            strength=strength,
            confidence=confidence,
        )

    @staticmethod
    def record(
        store: MarketMemoryStore,
        decision: TradeDecisionSnapshot,
    ) -> MemoryItem:
        item = DecisionAdapter.to_item(decision)
        store.append(item)
        return item
