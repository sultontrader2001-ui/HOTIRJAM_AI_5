"""Tests for Market Memory v1 Foundation (Sprint 41) — passive only."""

from __future__ import annotations

import pytest

from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.liquidity.models import LiquidityBias, LiquiditySnapshot
from hotirjam_ai5.live_data.dom import DomSnapshot
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.market_behavior.models import (
    BehaviorDirection,
    BehaviorSnapshot,
    MarketBehavior,
)
from hotirjam_ai5.market_state.models import (
    MarketDirection,
    MarketState,
    MarketStateSnapshot,
)
from hotirjam_ai5.memory import (
    BehaviorAdapter,
    DecisionAdapter,
    LiquidityAdapter,
    MarketMemoryStore,
    MemoryItem,
    MemorySource,
    PhysicsAdapter,
    StateAdapter,
)
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot


def _item(
    *,
    timestamp: float,
    source: MemorySource = MemorySource.PHYSICS,
    direction: str = "UP",
    strength: float = 1.0,
    confidence: float = 1.0,
) -> MemoryItem:
    return MemoryItem(
        timestamp=timestamp,
        source=source,
        direction=direction,
        strength=strength,
        confidence=confidence,
    )


def test_memory_append_and_ordering() -> None:
    store = MarketMemoryStore(capacity=10)
    store.append(_item(timestamp=1.0, direction="UP"))
    store.append(_item(timestamp=2.0, direction="DOWN"))
    store.append(_item(timestamp=3.0, direction="UP"))
    items = store.items()
    assert len(items) == 3
    assert [i.timestamp for i in items] == [1.0, 2.0, 3.0]
    assert items[0].direction == "UP"
    assert items[1].direction == "DOWN"


def test_ring_buffer_overflow_drops_oldest() -> None:
    store = MarketMemoryStore(capacity=3)
    for ts in (1.0, 2.0, 3.0, 4.0, 5.0):
        store.append(_item(timestamp=ts, strength=float(ts)))
    items = store.items()
    assert store.size == 3
    assert [i.timestamp for i in items] == [3.0, 4.0, 5.0]
    diag = store.diagnostics()
    assert diag.memory_size == 3
    assert diag.oldest_timestamp == 3.0
    assert diag.newest_timestamp == 5.0


def test_timestamp_ordering_preserved_on_append() -> None:
    store = MarketMemoryStore(capacity=100)
    timestamps = [10.0, 10.5, 11.0, 20.0]
    for ts in timestamps:
        store.append(_item(timestamp=ts))
    assert [i.timestamp for i in store.items()] == timestamps


def test_append_only_items_are_frozen() -> None:
    item = _item(timestamp=1.0)
    with pytest.raises(Exception):
        item.direction = "DOWN"  # type: ignore[misc]
    store = MarketMemoryStore(capacity=5)
    store.append(item)
    with pytest.raises(TypeError):
        store.append({"timestamp": 1.0})  # type: ignore[arg-type]


def test_diagnostics_records_by_source() -> None:
    store = MarketMemoryStore(capacity=20)
    store.append(_item(timestamp=1.0, source=MemorySource.PHYSICS))
    store.append(_item(timestamp=2.0, source=MemorySource.LIQUIDITY))
    store.append(_item(timestamp=3.0, source=MemorySource.PHYSICS))
    diag = store.diagnostics()
    assert diag.records_by_source[MemorySource.PHYSICS] == 2
    assert diag.records_by_source[MemorySource.LIQUIDITY] == 1
    assert diag.records_by_source[MemorySource.STATE] == 0
    assert diag.oldest_timestamp == 1.0
    assert diag.newest_timestamp == 3.0


def test_physics_adapter() -> None:
    physics = PhysicsSnapshot(
        spread=0.25,
        mid_price=100.0,
        tick_velocity=2.5,
        tick_acceleration=0.5,
        tick_count=3,
    )
    item = PhysicsAdapter.to_item(physics, timestamp=42.0)
    assert item is not None
    assert item.source is MemorySource.PHYSICS
    assert item.direction == "UP"
    assert item.strength == pytest.approx(3.0)
    assert item.confidence == 1.0
    assert PhysicsAdapter.to_item(
        PhysicsSnapshot(tick_count=0), timestamp=1.0
    ) is None


def test_liquidity_adapter() -> None:
    snap = LiquiditySnapshot(
        timestamp=5.0,
        liquidity_shift=LiquidityBias.BUY.value,
        dom_imbalance=LiquidityBias.BUY.value,
        confidence=0.8,
    )
    item = LiquidityAdapter.to_item(snap)
    assert item.source is MemorySource.LIQUIDITY
    assert item.direction == "BUY"
    assert item.strength == pytest.approx(0.8)
    assert item.confidence == pytest.approx(0.8)


def test_state_and_behavior_adapters() -> None:
    state = MarketStateSnapshot(
        state=MarketState.TRENDING,
        reason="fixture",
        timestamp=7.0,
        direction=MarketDirection.UP,
    )
    s_item = StateAdapter.to_item(state)
    assert s_item is not None
    assert s_item.source is MemorySource.STATE
    assert s_item.direction == "UP"
    assert s_item.strength == pytest.approx(0.9)

    behavior = BehaviorSnapshot(
        behavior=MarketBehavior.ACCELERATING,
        reason="fixture",
        timestamp=8.0,
        direction=BehaviorDirection.BUY,
    )
    b_item = BehaviorAdapter.to_item(behavior)
    assert b_item is not None
    assert b_item.source is MemorySource.BEHAVIOR
    assert b_item.direction == "BUY"


def test_decision_adapter() -> None:
    snap = TradeDecisionSnapshot(
        timestamp=9.0,
        decision=TradeDecision.BUY_INTERNAL,
        reason="fixture",
        next_action="Execution Engine",
        buy_score=100,
        buy_confidence=92,
        sell_score=35,
        sell_confidence=40,
    )
    item = DecisionAdapter.to_item(snap)
    assert item.source is MemorySource.DECISION
    assert item.direction == "BUY"
    assert item.strength == pytest.approx(100.0)
    assert item.confidence == pytest.approx(0.92)


def test_controller_fills_memory_without_changing_dashboard_shape() -> None:
    clock = iter([100.0 + i * 0.1 for i in range(50)]).__next__
    controller = DashboardController(wall_clock=clock)
    controller.start()
    for i in range(5):
        controller.on_tick(
            LiveTick(
                timestamp=100.0 + i,
                symbol="MNQ",
                last_price=20000.0 + i,
                bid=19999.75 + i,
                ask=20000.25 + i,
                volume=1,
            )
        )
    controller.on_dom(
        DomSnapshot(
            timestamp_utc="2026-07-21T00:00:00.0000000Z",
            instrument="MNQ",
            depth_levels=5,
            best_bid_size=10,
            best_ask_size=4,
            total_bid_size=40,
            total_ask_size=20,
            status="OK",
        )
    )
    state = controller.snapshot()
    assert state.trade_decision.decision in {
        "NO_TRADE",
        "BUY_INTERNAL",
        "SELL_INTERNAL",
    }
    diag = controller.memory_diagnostics
    assert diag.memory_size >= 1
    assert diag.records_by_source[MemorySource.PHYSICS] >= 1
    assert diag.records_by_source[MemorySource.LIQUIDITY] >= 1
    assert diag.records_by_source[MemorySource.DECISION] >= 1
    assert diag.oldest_timestamp is not None
    assert diag.newest_timestamp is not None
    # Dashboard models unchanged — no memory section required.
    assert not hasattr(state, "memory")


def test_trade_decision_unaffected_by_memory_contents() -> None:
    """Pre-filled memory must not change decision output."""
    empty = DashboardController()
    filled = DashboardController()
    for i in range(20):
        filled.memory_store.append(
            _item(
                timestamp=float(i),
                source=MemorySource.PHYSICS,
                direction="DOWN",
                strength=99.0,
            )
        )
    tick = LiveTick(
        timestamp=1.0,
        symbol="MNQ",
        last_price=20100.0,
        bid=20099.75,
        ask=20100.25,
        volume=1,
    )
    empty.on_tick(tick)
    filled.on_tick(tick)
    a = empty.snapshot().trade_decision
    b = filled.snapshot().trade_decision
    assert a.decision == b.decision
    assert a.buy_score == b.buy_score
    assert a.sell_score == b.sell_score
    assert a.buy_confidence == b.buy_confidence
    assert a.sell_confidence == b.sell_confidence
