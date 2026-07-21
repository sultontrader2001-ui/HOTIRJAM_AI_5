"""Assemble InitiativeSnapshot from evidence and lifecycle state."""

from __future__ import annotations

from hotirjam_ai5.initiative.initiative_models import (
    InitiativeEvidence,
    InitiativeSide,
    InitiativeState,
)
from hotirjam_ai5.initiative.initiative_snapshot import InitiativeSnapshot

# Intensity floors / bands for auction-control observation.
_MIN_ACTIVITY = 12.0
_EMERGING_MIN = 18.0
_DOMINANT_MIN = 55.0
_SEPARATION_MIN = 8.0


def select_dominant_side(buyer: float, seller: float) -> InitiativeSide:
    """Choose Dominant Side from intensities only. Never uses Objective."""
    lead = max(buyer, seller)
    if lead < _MIN_ACTIVITY:
        return InitiativeSide.NONE
    if buyer >= seller + _SEPARATION_MIN and buyer >= _EMERGING_MIN:
        return InitiativeSide.BUYER
    if seller >= buyer + _SEPARATION_MIN and seller >= _EMERGING_MIN:
        return InitiativeSide.SELLER
    return InitiativeSide.NONE


def dominant_intensity(side: InitiativeSide, buyer: float, seller: float) -> float:
    if side is InitiativeSide.BUYER:
        return buyer
    if side is InitiativeSide.SELLER:
        return seller
    return max(buyer, seller)


def advance_lifecycle(
    previous: InitiativeState,
    *,
    side: InitiativeSide,
    intensity: float,
    buyer: float,
    seller: float,
) -> InitiativeState:
    """Exact H-5 lifecycle transitions from market-control evidence."""
    separation = abs(buyer - seller)
    has_control = side is not InitiativeSide.NONE
    strong = has_control and intensity >= _DOMINANT_MIN and separation >= _SEPARATION_MIN
    emerging = has_control and intensity >= _EMERGING_MIN
    fading = has_control and intensity < _DOMINANT_MIN

    if previous is InitiativeState.EXPIRED:
        if strong:
            return InitiativeState.DOMINANT
        if emerging:
            return InitiativeState.EMERGING
        return InitiativeState.NONE

    if not has_control:
        if previous in {
            InitiativeState.EMERGING,
            InitiativeState.DOMINANT,
            InitiativeState.WEAKENING,
        }:
            return InitiativeState.EXPIRED
        return InitiativeState.NONE

    if previous is InitiativeState.NONE:
        return InitiativeState.DOMINANT if strong else InitiativeState.EMERGING

    if previous is InitiativeState.EMERGING:
        if strong:
            return InitiativeState.DOMINANT
        if emerging:
            return InitiativeState.EMERGING
        return InitiativeState.EXPIRED

    if previous is InitiativeState.DOMINANT:
        if strong:
            return InitiativeState.DOMINANT
        if fading:
            return InitiativeState.WEAKENING
        return InitiativeState.EXPIRED

    if previous is InitiativeState.WEAKENING:
        if strong:
            return InitiativeState.DOMINANT
        if emerging:
            return InitiativeState.WEAKENING
        return InitiativeState.EXPIRED

    return InitiativeState.NONE


def confidence_from_evidence(
    *,
    evidence: InitiativeEvidence,
    side: InitiativeSide,
    buyer: float,
    seller: float,
) -> float:
    """Confidence from evidence quality. Context may raise it; never chooses side."""
    if side is InitiativeSide.NONE and max(buyer, seller) < _MIN_ACTIVITY:
        base = max(0.0, evidence.energy * 0.25)
        return min(100.0, base + evidence.context * 0.5)

    channels = (
        evidence.force,
        evidence.motion,
        evidence.pressure,
        evidence.liquidity,
        evidence.energy,
    )
    active = [value for value in channels if value >= 15.0]
    agreement = (len(active) / len(channels)) * 70.0
    separation = min(30.0, abs(buyer - seller))
    confidence = agreement + separation * 0.5 + evidence.context * 0.4
    return max(0.0, min(100.0, confidence))


def assemble_snapshot(
    *,
    buyer: float,
    seller: float,
    side: InitiativeSide,
    state: InitiativeState,
    evidence: InitiativeEvidence,
    reasons: tuple[str, ...],
    timestamp: float,
) -> InitiativeSnapshot:
    confidence = confidence_from_evidence(
        evidence=evidence, side=side, buyer=buyer, seller=seller
    )
    ordered = list(reasons)
    ordered.append(f"Buyer initiative {buyer:.1f}")
    ordered.append(f"Seller initiative {seller:.1f}")
    ordered.append(f"Dominant side {side.value}")
    ordered.append(f"Initiative state {state.value}")
    ordered.extend(evidence.summary_lines())
    return InitiativeSnapshot(
        buyer_initiative=buyer,
        seller_initiative=seller,
        dominant_side=side,
        initiative_state=state,
        confidence=confidence,
        evidence=evidence,
        reasons=tuple(ordered),
        timestamp=timestamp,
    )
