"""Unit tests for Liquidity Engine (Sprint 27)."""

from __future__ import annotations

from hotirjam_ai5.live_data.dom import DomSnapshot
from hotirjam_ai5.liquidity import LiquidityBias, LiquidityEngine, LiquiditySnapshot
from hotirjam_ai5.liquidity.classifier import classify_bias, imbalance_confidence


def _dom(
    *,
    total_bid: int = 100,
    total_ask: int = 50,
    best_bid: int | None = 20,
    best_ask: int | None = 10,
    instrument: str = "MNQ",
) -> DomSnapshot:
    return DomSnapshot(
        timestamp_utc="2026-07-21T00:00:00Z",
        instrument=instrument,
        depth_levels=10,
        best_bid_size=best_bid,
        best_ask_size=best_ask,
        total_bid_size=total_bid,
        total_ask_size=total_ask,
        status="OK",
    )


def test_classify_bias_buy_sell_neutral() -> None:
    assert classify_bias(10, 5) is LiquidityBias.BUY
    assert classify_bias(5, 10) is LiquidityBias.SELL
    assert classify_bias(8, 8) is LiquidityBias.NEUTRAL


def test_imbalance_confidence_bounds() -> None:
    assert imbalance_confidence(0, 0) == 0.0
    assert imbalance_confidence(100, 0) == 1.0
    assert imbalance_confidence(50, 50) == 0.0
    assert 0.0 < imbalance_confidence(75, 25) < 1.0


def test_healthy_dom_produces_buy_liquidity() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = LiquidityEngine(clock=clock)
    snap = engine.on_dom(_dom(total_bid=120, total_ask=40, best_bid=30, best_ask=10))
    assert isinstance(snap, LiquiditySnapshot)
    assert snap.liquidity_shift == LiquidityBias.BUY.value
    assert snap.dom_imbalance == LiquidityBias.BUY.value
    assert snap.confidence == imbalance_confidence(120, 40)
    assert snap.timestamp == 10.0
    assert engine.snapshot() is snap


def test_healthy_dom_produces_sell_liquidity() -> None:
    engine = LiquidityEngine(clock=lambda: 20.0)
    snap = engine.on_dom(_dom(total_bid=30, total_ask=90, best_bid=5, best_ask=25))
    assert snap.liquidity_shift == LiquidityBias.SELL.value
    assert snap.dom_imbalance == LiquidityBias.SELL.value
    assert snap.confidence == imbalance_confidence(30, 90)


def test_missing_dom_clears_snapshot() -> None:
    engine = LiquidityEngine(clock=lambda: 1.0)
    assert engine.snapshot() is None
    engine.on_dom(_dom())
    assert engine.snapshot() is not None
    engine.clear()
    assert engine.snapshot() is None


def test_best_size_fallback_to_totals() -> None:
    engine = LiquidityEngine(clock=lambda: 3.0)
    snap = engine.on_dom(
        _dom(total_bid=80, total_ask=20, best_bid=None, best_ask=None)
    )
    assert snap.liquidity_shift == LiquidityBias.BUY.value
    assert snap.dom_imbalance == LiquidityBias.BUY.value
