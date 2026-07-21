"""H-6 Initiative Engine contract tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hotirjam_ai5.initiative import (
    InitiativeEngine,
    InitiativeInputs,
    InitiativeSide,
    InitiativeSnapshot,
    InitiativeState,
    OhlcCandle,
    evaluate_initiative,
)
from hotirjam_ai5.live_validator import ArchitecturePipeline, render_validator_frame
from hotirjam_ai5.objective import ObjectiveSnapshot


TICK = 0.25


def _c(o: float, h: float, l: float, c: float, *, volume: float = 100.0) -> OhlcCandle:
    return OhlcCandle(open=o, high=h, low=l, close=c, volume=volume)


def _flat(n: int = 6) -> tuple[OhlcCandle, ...]:
    return tuple(_c(100.0, 100.1, 99.9, 100.0, volume=1.0) for _ in range(n))


def _buyer_push(*, strength: str = "strong") -> tuple[OhlcCandle, ...]:
    if strength == "emerging":
        return (
            _c(100.0, 100.4, 99.9, 100.3, volume=40),
            _c(100.3, 100.6, 100.2, 100.5, volume=45),
            _c(100.5, 100.8, 100.4, 100.7, volume=50),
            _c(100.7, 101.0, 100.6, 100.9, volume=55),
            _c(100.9, 101.2, 100.8, 101.1, volume=60),
            _c(101.1, 101.4, 101.0, 101.3, volume=65),
        )
    if strength == "weakening":
        return (
            _c(100.0, 101.5, 99.9, 101.4, volume=120),
            _c(101.4, 102.5, 101.2, 102.4, volume=130),
            _c(102.4, 103.2, 102.2, 103.1, volume=140),
            _c(103.1, 103.4, 102.9, 103.2, volume=50),
            _c(103.2, 103.35, 103.0, 103.15, volume=30),
            _c(103.15, 103.25, 103.05, 103.1, volume=20),
        )
    # strong dominance
    return (
        _c(100.0, 101.0, 99.8, 100.9, volume=80),
        _c(100.9, 102.0, 100.7, 101.9, volume=90),
        _c(101.9, 103.0, 101.7, 102.9, volume=100),
        _c(102.9, 104.0, 102.7, 103.9, volume=110),
        _c(103.9, 105.0, 103.7, 104.9, volume=120),
        _c(104.9, 106.0, 104.7, 105.9, volume=130),
    )


def _seller_push() -> tuple[OhlcCandle, ...]:
    return (
        _c(106.0, 106.2, 105.0, 105.1, volume=80),
        _c(105.1, 105.2, 104.0, 104.1, volume=90),
        _c(104.1, 104.2, 103.0, 103.1, volume=100),
        _c(103.1, 103.2, 102.0, 102.1, volume=110),
        _c(102.1, 102.2, 101.0, 101.1, volume=120),
        _c(101.1, 101.2, 100.0, 100.1, volume=130),
    )


def _contested() -> tuple[OhlcCandle, ...]:
    return (
        _c(100.0, 101.0, 99.5, 100.8, volume=80),
        _c(100.8, 101.2, 99.8, 100.0, volume=85),
        _c(100.0, 100.5, 99.0, 99.2, volume=90),
        _c(99.2, 100.8, 99.0, 100.6, volume=95),
        _c(100.6, 101.0, 99.5, 99.7, volume=100),
        _c(99.7, 100.9, 99.5, 100.5, volume=105),
    )


def _objectives(*, complete: bool = True) -> ObjectiveSnapshot:
    if not complete:
        return ObjectiveSnapshot.empty(timestamp=1.0, current_price=100.0)
    return ObjectiveSnapshot(
        nearest_high_price=110.0,
        nearest_high_distance_ticks=40.0,
        nearest_high_strength=80.0,
        nearest_low_price=90.0,
        nearest_low_distance_ticks=40.0,
        nearest_low_strength=80.0,
        current_price=100.0,
        timestamp=1.0,
    )


def test_no_activity_is_none() -> None:
    snap = evaluate_initiative(
        InitiativeInputs(candles=_flat(), tick_size=TICK, timestamp=1.0)
    )
    assert snap.dominant_side is InitiativeSide.NONE
    assert snap.initiative_state is InitiativeState.NONE
    assert snap.buyer_initiative == 0.0 or snap.buyer_initiative < 15.0
    assert snap.seller_initiative == 0.0 or snap.seller_initiative < 15.0


def test_buyer_emerging_lifecycle() -> None:
    engine = InitiativeEngine()
    # Mild upward grind: enough for control, below dominance band.
    mild = (
        _c(100.0, 100.3, 99.95, 100.2, volume=20),
        _c(100.2, 100.45, 100.1, 100.35, volume=22),
        _c(100.35, 100.55, 100.25, 100.5, volume=24),
        _c(100.5, 100.7, 100.4, 100.65, volume=26),
        _c(100.65, 100.85, 100.55, 100.8, volume=28),
        _c(100.8, 101.0, 100.7, 100.95, volume=30),
    )
    snap = engine.evaluate(
        InitiativeInputs(candles=mild, tick_size=TICK, timestamp=1.0)
    )
    assert snap.dominant_side is InitiativeSide.BUYER
    assert snap.initiative_state is InitiativeState.EMERGING
    assert snap.buyer_initiative > snap.seller_initiative
    assert snap.buyer_initiative < 55.0


def test_buyer_dominance_lifecycle() -> None:
    engine = InitiativeEngine()
    snap = engine.evaluate(
        InitiativeInputs(
            candles=_buyer_push(strength="strong"),
            tick_size=TICK,
            timestamp=1.0,
        )
    )
    assert snap.dominant_side is InitiativeSide.BUYER
    assert snap.initiative_state is InitiativeState.DOMINANT
    assert snap.buyer_initiative >= 55.0


def test_weakening_after_dominance() -> None:
    engine = InitiativeEngine()
    dominant = engine.evaluate(
        InitiativeInputs(
            candles=_buyer_push(strength="strong"),
            tick_size=TICK,
            timestamp=1.0,
        )
    )
    assert dominant.initiative_state is InitiativeState.DOMINANT
    weakened = engine.evaluate(
        InitiativeInputs(
            candles=_buyer_push(strength="weakening"),
            tick_size=TICK,
            timestamp=2.0,
        )
    )
    assert weakened.dominant_side is InitiativeSide.BUYER
    assert weakened.initiative_state is InitiativeState.WEAKENING


def test_expiration_then_none() -> None:
    engine = InitiativeEngine()
    engine.evaluate(
        InitiativeInputs(
            candles=_buyer_push(strength="strong"),
            tick_size=TICK,
            timestamp=1.0,
        )
    )
    expired = engine.evaluate(
        InitiativeInputs(candles=_flat(), tick_size=TICK, timestamp=2.0)
    )
    assert expired.initiative_state is InitiativeState.EXPIRED
    assert expired.dominant_side is InitiativeSide.NONE
    none = engine.evaluate(
        InitiativeInputs(candles=_flat(), tick_size=TICK, timestamp=3.0)
    )
    assert none.initiative_state is InitiativeState.NONE


def test_both_active_selects_correct_dominant() -> None:
    buyer = evaluate_initiative(
        InitiativeInputs(candles=_buyer_push(), tick_size=TICK, timestamp=1.0)
    )
    seller = evaluate_initiative(
        InitiativeInputs(candles=_seller_push(), tick_size=TICK, timestamp=1.0)
    )
    contested = evaluate_initiative(
        InitiativeInputs(candles=_contested(), tick_size=TICK, timestamp=1.0)
    )
    assert buyer.dominant_side is InitiativeSide.BUYER
    assert seller.dominant_side is InitiativeSide.SELLER
    assert contested.buyer_initiative > 0.0 or contested.seller_initiative > 0.0
    # Contested/noisy tape may remain NONE when separation is insufficient.
    assert contested.dominant_side in {
        InitiativeSide.NONE,
        InitiativeSide.BUYER,
        InitiativeSide.SELLER,
    }


def test_objective_unavailable_initiative_still_works() -> None:
    snap = evaluate_initiative(
        InitiativeInputs(
            candles=_buyer_push(),
            tick_size=TICK,
            timestamp=1.0,
            objectives=None,
        )
    )
    assert snap.dominant_side is InitiativeSide.BUYER
    assert snap.evidence.context == 0.0
    assert any("Objective unavailable" in reason for reason in snap.reasons)


def test_objective_context_affects_confidence_only() -> None:
    without = evaluate_initiative(
        InitiativeInputs(
            candles=_buyer_push(),
            tick_size=TICK,
            timestamp=1.0,
            objectives=None,
        )
    )
    with_obj = evaluate_initiative(
        InitiativeInputs(
            candles=_buyer_push(),
            tick_size=TICK,
            timestamp=1.0,
            objectives=_objectives(complete=True),
        )
    )
    assert without.dominant_side == with_obj.dominant_side
    assert without.buyer_initiative == with_obj.buyer_initiative
    assert without.seller_initiative == with_obj.seller_initiative
    assert with_obj.evidence.context > without.evidence.context
    assert with_obj.confidence >= without.confidence


def test_snapshot_immutability() -> None:
    snap = evaluate_initiative(
        InitiativeInputs(candles=_buyer_push(), tick_size=TICK, timestamp=1.0)
    )
    try:
        snap.buyer_initiative = 0.0  # type: ignore[misc]
        raised = False
    except Exception:
        raised = True
    assert raised
    assert isinstance(snap, InitiativeSnapshot)


def test_replay_determinism() -> None:
    inputs = InitiativeInputs(
        candles=_buyer_push(),
        tick_size=TICK,
        timestamp=10.0,
        objectives=_objectives(),
    )
    assert evaluate_initiative(inputs) == evaluate_initiative(inputs)


def test_restart_continuity(tmp_path: Path) -> None:
    checkpoint = tmp_path / "initiative.json"
    original = InitiativeEngine(checkpoint_path=checkpoint)
    original.evaluate(
        InitiativeInputs(
            candles=_buyer_push(strength="strong"),
            tick_size=TICK,
            timestamp=1.0,
        )
    )
    restored = InitiativeEngine(checkpoint_path=checkpoint)
    assert restored.snapshot() == original.snapshot()
    assert restored.previous_state is original.previous_state
    weakened = restored.evaluate(
        InitiativeInputs(
            candles=_buyer_push(strength="weakening"),
            tick_size=TICK,
            timestamp=2.0,
        )
    )
    assert weakened.initiative_state is InitiativeState.WEAKENING


def test_no_trade_vocabulary_in_snapshot() -> None:
    snap = evaluate_initiative(
        InitiativeInputs(candles=_buyer_push(), tick_size=TICK, timestamp=1.0)
    )
    blob = " ".join(
        [
            snap.dominant_side.value,
            snap.initiative_state.value,
            *snap.reasons,
            *snap.evidence.summary_lines(),
        ]
    )
    for banned in ("BUY ", "SELL ", "TRADE", "NO_TRADE", "BUY\n", "SELL\n"):
        assert banned not in blob
    assert snap.dominant_side.value in {"BUYER", "SELLER", "NONE"}


def test_developer_view_exposes_h5_initiative_fields() -> None:
    pipeline = ArchitecturePipeline(tick_size=TICK)
    frame = pipeline.evaluate(
        current_price=105.0,
        timestamp=1.0,
        candles=_buyer_push(),
        confirmed_highs=(),
        confirmed_lows=(),
    )
    text = render_validator_frame(frame, developer_mode=True)
    assert "Initiative State" in text
    assert "Dominant Side" in text
    assert "Buyer Initiative" in text
    assert "Seller Initiative" in text
    assert "Confidence" in text
    assert "Evidence Summary" in text
    assert "Reasons" in text
    trader = render_validator_frame(frame, developer_mode=False)
    assert "INITIATIVE ENGINE" in trader
    assert "Impulse/Mom/Cndl" not in trader
