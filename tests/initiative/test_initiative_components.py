"""Component-level tests for Initiative submodules."""

from __future__ import annotations

from hotirjam_ai5.initiative import (
    ImpulseResult,
    ImpulseSide,
    InitiativeSide,
    InitiativeState,
    MomentumResult,
    MomentumState,
    CandleStrengthResult,
    score_initiative,
)
from hotirjam_ai5.initiative.impulse_detector import detect_impulse
from hotirjam_ai5.initiative.momentum_detector import detect_momentum
from hotirjam_ai5.initiative.candle_strength import analyze_candle_strength
from hotirjam_ai5.initiative.initiative_models import OhlcCandle
from hotirjam_ai5.objective import ObjectiveSnapshot


def _c(o: float, h: float, l: float, c: float) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=10.0)


def test_impulse_insufficient_candles() -> None:
    result = detect_impulse((_c(100, 101, 99, 100.5),), tick_size=0.25)
    assert result.side is ImpulseSide.NONE


def test_momentum_insufficient_candles() -> None:
    result = detect_momentum(
        (_c(100, 101, 99, 100.5), _c(100.5, 101, 100, 100.8), _c(100.8, 101, 100, 100.9)),
        tick_size=0.25,
    )
    assert result.state is MomentumState.LOW


def test_candle_strength_empty() -> None:
    result = analyze_candle_strength(())
    assert result.score == 0.0
    assert result.direction is ImpulseSide.NONE


def test_scorer_combines_buyer_agreement() -> None:
    snap = score_initiative(
        impulse=ImpulseResult(ImpulseSide.BUY, 80.0, ("imp",)),
        momentum=MomentumResult(70.0, MomentumState.HIGH, ImpulseSide.BUY, ("mom",)),
        candles=CandleStrengthResult(60.0, ImpulseSide.BUY, ("cndl",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=99.0,
    )
    assert snap.initiative_side is InitiativeSide.BUYER
    assert snap.state in {InitiativeState.MEDIUM, InitiativeState.STRONG}
    assert snap.confidence == 100.0
    assert snap.timestamp == 99.0


def test_scorer_forces_none_on_negligible_score() -> None:
    snap = score_initiative(
        impulse=ImpulseResult(ImpulseSide.BUY, 5.0, ("imp",)),
        momentum=MomentumResult(5.0, MomentumState.LOW, ImpulseSide.BUY, ("mom",)),
        candles=CandleStrengthResult(5.0, ImpulseSide.BUY, ("cndl",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=1.0,
    )
    assert snap.initiative_side is InitiativeSide.NONE
    assert snap.state is InitiativeState.WEAK


def test_scorer_strong_state_and_momentum_fallback() -> None:
    # Momentum fallback when impulse is NONE.
    fallback = score_initiative(
        impulse=ImpulseResult(ImpulseSide.NONE, 0.0, ("no impulse",)),
        momentum=MomentumResult(90.0, MomentumState.HIGH, ImpulseSide.SELL, ("mom",)),
        candles=CandleStrengthResult(40.0, ImpulseSide.SELL, ("cndl",)),
        objectives=ObjectiveSnapshot(
            nearest_high_price=105.0,
            nearest_high_distance_ticks=20.0,
            nearest_high_strength=50.0,
            nearest_low_price=95.0,
            nearest_low_distance_ticks=20.0,
            nearest_low_strength=50.0,
            current_price=100.0,
            timestamp=1.0,
        ),
        timestamp=1.0,
    )
    assert fallback.initiative_side is InitiativeSide.SELLER
    assert fallback.state is InitiativeState.MEDIUM
    assert any("momentum" in r.lower() for r in fallback.reasons)

    strong = score_initiative(
        impulse=ImpulseResult(ImpulseSide.BUY, 95.0, ("imp",)),
        momentum=MomentumResult(90.0, MomentumState.HIGH, ImpulseSide.BUY, ("mom",)),
        candles=CandleStrengthResult(80.0, ImpulseSide.BUY, ("cndl",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=1.0,
    )
    assert strong.state is InitiativeState.STRONG
    assert strong.initiative_side is InitiativeSide.BUYER


def test_scorer_candle_fallback_side() -> None:
    snap = score_initiative(
        impulse=ImpulseResult(ImpulseSide.NONE, 0.0, ("no impulse",)),
        momentum=MomentumResult(10.0, MomentumState.LOW, ImpulseSide.NONE, ("mom",)),
        candles=CandleStrengthResult(80.0, ImpulseSide.BUY, ("cndl",)),
        objectives=ObjectiveSnapshot.empty(timestamp=1.0),
        timestamp=1.0,
    )
    assert snap.initiative_side is InitiativeSide.BUYER
    assert any("candle" in r.lower() for r in snap.reasons)


def test_impulse_invalid_tick_and_conflict() -> None:
    assert detect_impulse((_c(100, 101, 99, 101), _c(101, 102, 100, 102)), tick_size=-1).side is ImpulseSide.NONE
    # Up net move but majority bearish bodies → conflict / NONE
    conflict = (
        _c(100.0, 101.0, 99.5, 99.6),  # bearish
        _c(99.6, 100.0, 99.0, 99.2),   # bearish
        _c(99.2, 103.0, 99.0, 102.5),  # big bullish → net up, bodies bearish majority
    )
    result = detect_impulse(conflict, tick_size=0.25)
    assert result.side is ImpulseSide.NONE


def test_momentum_invalid_tick_and_sell() -> None:
    assert detect_momentum((_c(100, 101, 99, 100),) * 4, tick_size=0.0).state is MomentumState.LOW
    down = (
        _c(110, 110.5, 109, 109.5),
        _c(109.5, 110, 108, 108.5),
        _c(108.5, 109, 107, 107.5),
        _c(107.5, 108, 105, 105.5),
        _c(105.5, 106, 103, 103.5),
        _c(103.5, 104, 100, 100.5),
    )
    result = detect_momentum(down, tick_size=0.25)
    assert result.direction is ImpulseSide.SELL


def test_candle_strength_zero_range() -> None:
    flat = (_c(100.0, 100.0, 100.0, 100.0),) * 3
    result = analyze_candle_strength(flat)
    assert result.score >= 0.0
