"""IN04 — Initiative Scorer.

Combines Impulse, Momentum, and Candle Strength into one initiative view.
Does not check breakouts. Does not emit trade decisions.
"""

from __future__ import annotations

from hotirjam_ai5.initiative.initiative_models import (
    CandleStrengthResult,
    ImpulseResult,
    ImpulseSide,
    InitiativeSide,
    InitiativeState,
    MomentumResult,
)
from hotirjam_ai5.initiative.initiative_snapshot import InitiativeSnapshot
from hotirjam_ai5.objective import ObjectiveSnapshot


def _side_from_impulse(side: ImpulseSide) -> InitiativeSide:
    if side is ImpulseSide.BUY:
        return InitiativeSide.BUYER
    if side is ImpulseSide.SELL:
        return InitiativeSide.SELLER
    return InitiativeSide.NONE


def _state_from_score(score: float) -> InitiativeState:
    if score < 35.0:
        return InitiativeState.WEAK
    if score < 70.0:
        return InitiativeState.MEDIUM
    return InitiativeState.STRONG


def _agreement(
    impulse: ImpulseResult,
    momentum: MomentumResult,
    candles: CandleStrengthResult,
) -> float:
    """0–100 confidence from component agreement."""
    sides = [impulse.side, momentum.direction, candles.direction]
    active = [s for s in sides if s is not ImpulseSide.NONE]
    if not active:
        return 0.0
    buy = sum(1 for s in active if s is ImpulseSide.BUY)
    sell = sum(1 for s in active if s is ImpulseSide.SELL)
    majority = max(buy, sell)
    return (majority / len(active)) * 100.0


def score_initiative(
    *,
    impulse: ImpulseResult,
    momentum: MomentumResult,
    candles: CandleStrengthResult,
    objectives: ObjectiveSnapshot,
    timestamp: float,
) -> InitiativeSnapshot:
    """Produce InitiativeSnapshot from the three detectors."""
    reasons: list[str] = []
    reasons.extend(impulse.reasons)
    reasons.extend(momentum.reasons)
    reasons.extend(candles.reasons)

    initiative_score = (
        0.40 * impulse.score
        + 0.35 * momentum.score
        + 0.25 * candles.score
    )
    initiative_score = max(0.0, min(100.0, initiative_score))

    # Side: impulse leads; if NONE, fall back to momentum then candles.
    if impulse.side is not ImpulseSide.NONE:
        side = _side_from_impulse(impulse.side)
        reasons.append(f"Side from impulse ({impulse.side.value})")
    elif momentum.direction is not ImpulseSide.NONE and momentum.score >= 30.0:
        side = _side_from_impulse(momentum.direction)
        reasons.append(f"Side from momentum ({momentum.direction.value})")
    elif candles.direction is not ImpulseSide.NONE and candles.score >= 50.0:
        side = _side_from_impulse(candles.direction)
        reasons.append(f"Side from candle strength ({candles.direction.value})")
    else:
        side = InitiativeSide.NONE
        reasons.append("No clear initiative side")

    # Flat / weak: force NONE when score is negligible.
    if initiative_score < 15.0:
        side = InitiativeSide.NONE
        reasons.append("Initiative score below minimum")

    confidence = _agreement(impulse, momentum, candles)
    # Mild objective context boost when battlefield is known (not breakout logic).
    if objectives.is_complete and side is not InitiativeSide.NONE:
        confidence = min(100.0, confidence + 5.0)
        reasons.append("Objectives present — confidence reinforced")

    state = _state_from_score(initiative_score)
    if side is InitiativeSide.NONE:
        state = InitiativeState.WEAK

    return InitiativeSnapshot(
        initiative_side=side,
        impulse_score=impulse.score,
        momentum_score=momentum.score,
        candle_strength_score=candles.score,
        initiative_score=initiative_score,
        state=state,
        confidence=confidence,
        reasons=tuple(reasons),
        timestamp=timestamp,
    )
