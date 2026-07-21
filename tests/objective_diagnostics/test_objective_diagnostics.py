"""Tests for shared Objective structural classification and diagnostics."""

from __future__ import annotations

from hotirjam_ai5.objective import ConfirmedSwing, evaluate_objectives, ObjectiveInputs
from hotirjam_ai5.objective_diagnostics import (
    CandidateCategory,
    LifecycleState,
    ObjectiveDiagnosticsInputs,
    PersistentStructuralHierarchy,
    SwingSide,
    audit_objectives,
    build_hierarchy,
    format_audit_report,
)


TICK = 0.25


def _h(price: float, strength: float, *, at: float) -> ConfirmedSwing:
    return ConfirmedSwing(price=price, strength=strength, confirmed_at=at)


def _l(price: float, strength: float, *, at: float) -> ConfirmedSwing:
    return ConfirmedSwing(price=price, strength=strength, confirmed_at=at)


def test_hierarchy_assigns_parent_and_depth() -> None:
    highs = (
        _h(110.0, 80.0, at=1.0),  # parent
        _h(105.0, 50.0, at=2.0),  # nested under 110
    )
    lows = (_l(95.0, 70.0, at=1.5),)
    nodes = build_hierarchy(highs, lows)
    by_price = {n.swing.price: n for n in nodes}
    assert by_price[110.0].parent_swing_id is None
    assert by_price[110.0].depth == 0
    assert by_price[105.0].parent_swing_id == by_price[110.0].swing_id
    assert by_price[105.0].depth == 1


def test_audit_labels_nested_and_micro() -> None:
    report = audit_objectives(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(
                _h(112.0, 85.0, at=1.0),  # major candidate — far, deep prominence
                _h(101.0, 40.0, at=2.0),  # near micro / nested
            ),
            confirmed_lows=(
                _l(88.0, 80.0, at=1.2),
                _l(99.0, 35.0, at=2.2),
            ),
            timestamp=10.0,
        )
    )
    assert report.highs
    assert report.lows
    text = format_audit_report(report)
    assert "HIGHS" in text
    assert "LOWS" in text
    assert "ID " in text
    # Nested / weak near swing should carry rejection reasons in report.
    near_high = next(d for d in report.highs if d.price == 101.0)
    assert near_high.eligible is False
    assert near_high.rejection_reasons


def test_price_penetration_is_challenged_and_remains_eligible() -> None:
    report = audit_objectives(
        ObjectiveDiagnosticsInputs(
            current_price=106.0,
            tick_size=TICK,
            confirmed_highs=(_h(105.0, 70.0, at=1.0),),
            confirmed_lows=(_l(90.0, 70.0, at=1.0),),
            timestamp=10.0,
            session_high=106.0,
            session_low=95.0,
        )
    )
    high = report.highs[0]
    assert high.lifecycle is LifecycleState.CHALLENGED
    assert high.eligible is True
    assert high.rejection_reasons == ()


def test_superseded_lifecycle() -> None:
    hierarchy = PersistentStructuralHierarchy()
    hierarchy.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(_h(108.0, 60.0, at=1.0),),
            confirmed_lows=(_l(90.0, 70.0, at=1.0),),
            timestamp=9.0,
        )
    )
    report = hierarchy.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(
                _h(108.0, 60.0, at=1.0),
                _h(108.25, 65.0, at=2.0),  # within zone, later
            ),
            confirmed_lows=(_l(90.0, 70.0, at=1.0),),
            timestamp=10.0,
        )
    )
    early = next(d for d in report.highs if d.price == 108.0)
    assert early.lifecycle is LifecycleState.SUPERSEDED


def test_objective_engine_uses_shared_diagnostic_eligibility() -> None:
    """Guard: the nearer ineligible swing must not become the objective."""
    highs = (
        _h(110.0, 90.0, at=1.0),
        _h(101.0, 40.0, at=2.0),  # nearer but nested/ineligible
    )
    lows = (_l(99.0, 50.0, at=1.0),)
    snap = evaluate_objectives(
        ObjectiveInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=highs,
            confirmed_lows=lows,
            timestamp=1.0,
        )
    )
    assert snap.nearest_high_price == 110.0

    report = audit_objectives(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=highs,
            confirmed_lows=lows,
            timestamp=1.0,
        )
    )
    nearer = next(d for d in report.highs if d.price == 101.0)
    assert nearer.side is SwingSide.HIGH
    assert nearer.eligible is False
    assert snap.nearest_high_price == 110.0


def test_each_diagnostic_has_required_fields() -> None:
    report = audit_objectives(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(_h(105.0, 70.0, at=1.0),),
            confirmed_lows=(_l(95.0, 70.0, at=1.0),),
            timestamp=5.0,
        )
    )
    d = report.highs[0]
    assert d.swing_id >= 1
    assert d.side is SwingSide.HIGH
    assert d.price == 105.0
    assert d.confirmed_at == 1.0
    assert d.distance_ticks == (105.0 - 100.0) / TICK
    assert d.current_strength == 70.0
    assert d.hierarchy_depth >= 0
    assert 0.0 <= d.persistence <= 100.0
    assert d.prominence >= 0.0
    assert d.lifecycle in LifecycleState
    assert d.category in CandidateCategory
    assert isinstance(d.eligible, bool)
    assert isinstance(d.rejection_reasons, tuple)


def test_empty_inputs() -> None:
    report = audit_objectives(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(),
            confirmed_lows=(),
            timestamp=1.0,
        )
    )
    assert report.highs == ()
    assert report.lows == ()
    assert "HIGHS" in format_audit_report(report)
