"""Component-level Initiative evidence tests for H-6."""

from __future__ import annotations

from hotirjam_ai5.initiative import (
    CandleStrengthResult,
    ImpulseResult,
    ImpulseSide,
    MomentumResult,
    MomentumState,
    OhlcCandle,
    analyze_candle_strength,
    build_evidence,
    detect_impulse,
    select_dominant_side,
)
from hotirjam_ai5.initiative.initiative_models import InitiativeSide
from hotirjam_ai5.objective import ObjectiveSnapshot


def _c(o: float, h: float, l: float, c: float, *, volume: float = 50.0) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=volume)


def test_insufficient_candles_return_none_impulse() -> None:
    result = detect_impulse((_c(100, 100.5, 99.5, 100.2),), tick_size=0.25)
    assert result.side is ImpulseSide.NONE


def test_build_evidence_independent_channels() -> None:
    candles = (
        _c(100, 101, 99.8, 100.8, volume=80),
        _c(100.8, 102, 100.6, 101.8, volume=90),
        _c(101.8, 103, 101.6, 102.8, volume=100),
        _c(102.8, 104, 102.6, 103.8, volume=110),
        _c(103.8, 105, 103.6, 104.8, volume=120),
    )
    impulse = ImpulseResult(ImpulseSide.BUYER, 80.0, ("force",))
    momentum = MomentumResult(70.0, MomentumState.HIGH, ImpulseSide.BUYER, ("motion",))
    pressure = CandleStrengthResult(60.0, ImpulseSide.BUYER, ("pressure",))
    evidence, buyer, seller, reasons = build_evidence(
        impulse=impulse,
        momentum=momentum,
        candles=pressure,
        ohlc=candles,
        tick_size=0.25,
        objectives=None,
    )
    assert evidence.force == 80.0
    assert evidence.motion == 70.0
    assert evidence.pressure == 60.0
    assert evidence.liquidity >= 0.0
    assert evidence.energy >= 0.0
    assert evidence.context == 0.0
    assert buyer > seller
    assert any("Objective unavailable" in reason for reason in reasons)
    assert select_dominant_side(buyer, seller) is InitiativeSide.BUYER


def test_objective_context_only_in_evidence() -> None:
    candles = tuple(_c(100 + i, 100.5 + i, 99.8 + i, 100.4 + i) for i in range(5))
    objectives = ObjectiveSnapshot(
        nearest_high_price=110.0,
        nearest_high_distance_ticks=20.0,
        nearest_high_strength=70.0,
        nearest_low_price=90.0,
        nearest_low_distance_ticks=20.0,
        nearest_low_strength=70.0,
        current_price=100.0,
        timestamp=1.0,
    )
    impulse = ImpulseResult(ImpulseSide.BUYER, 50.0, ("force",))
    momentum = MomentumResult(50.0, MomentumState.MEDIUM, ImpulseSide.BUYER, ("motion",))
    pressure = analyze_candle_strength(candles)
    with_ctx, buyer_a, seller_a, _ = build_evidence(
        impulse=impulse,
        momentum=momentum,
        candles=pressure,
        ohlc=candles,
        tick_size=0.25,
        objectives=objectives,
    )
    without, buyer_b, seller_b, _ = build_evidence(
        impulse=impulse,
        momentum=momentum,
        candles=pressure,
        ohlc=candles,
        tick_size=0.25,
        objectives=None,
    )
    assert with_ctx.context > 0.0
    assert without.context == 0.0
    assert buyer_a == buyer_b
    assert seller_a == seller_b
    assert select_dominant_side(buyer_a, seller_a) == select_dominant_side(
        buyer_b, seller_b
    )
