"""Sprint H-4 regression contract for Objective lifecycle semantics."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from hotirjam_ai5.live_validator import ArchitecturePipeline, render_validator_frame
from hotirjam_ai5.objective import (
    ConfirmedSwing,
    ObjectivePersistenceState,
)
from hotirjam_ai5.objective_diagnostics import (
    LifecycleState,
    ObjectiveDiagnosticsInputs,
    PersistentStructuralHierarchy,
)


TICK = 0.25


def _swing(price: float, strength: float, at: float) -> ConfirmedSwing:
    return ConfirmedSwing(price=price, strength=strength, confirmed_at=at)


def _evaluate(
    pipeline: ArchitecturePipeline,
    *,
    price: float,
    timestamp: float,
    highs: tuple[ConfirmedSwing, ...],
    lows: tuple[ConfirmedSwing, ...],
):
    return pipeline.evaluate(
        current_price=price,
        timestamp=timestamp,
        candles=(),
        confirmed_highs=highs,
        confirmed_lows=lows,
    )


def _record(
    pipeline: ArchitecturePipeline, price: float
):
    return next(
        item
        for item in pipeline.structural_hierarchy.snapshot().records
        if item.price == price
    )


def test_new_transitions_to_active_with_explicit_journal_entries() -> None:
    hierarchy = PersistentStructuralHierarchy()
    hierarchy.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(_swing(110.0, 90.0, 1.0),),
            confirmed_lows=(),
            timestamp=10.0,
        )
    )
    transitions = hierarchy.journal
    assert transitions[0].old_state is None
    assert transitions[0].new_state["lifecycle"] == "NEW"
    assert transitions[0].cause == "SWING_CONFIRMED"
    assert transitions[1].old_state["lifecycle"] == "NEW"
    assert transitions[1].new_state["lifecycle"] == "ACTIVE"
    assert transitions[1].cause == "OBJECTIVE_STRUCTURE_ACTIVATED"


def test_liquidity_sweep_challenges_then_confirmed_reclaim_reactivates() -> None:
    pipeline = ArchitecturePipeline(tick_size=TICK)
    high = _swing(110.0, 90.0, 1.0)
    low = _swing(90.0, 80.0, 1.5)
    _evaluate(
        pipeline,
        price=100.0,
        timestamp=10.0,
        highs=(high,),
        lows=(low,),
    )

    swept = _evaluate(
        pipeline,
        price=110.25,
        timestamp=11.0,
        highs=(high,),
        lows=(low,),
    )
    challenged = _record(pipeline, 110.0)
    assert challenged.lifecycle is LifecycleState.CHALLENGED
    assert swept.objective.nearest_high_price == 110.0
    assert swept.objective.high_state is ObjectivePersistenceState.PERSISTED

    reclaim_low = _swing(109.0, 65.0, 3.0)
    reclaimed = _evaluate(
        pipeline,
        price=109.5,
        timestamp=12.0,
        highs=(high,),
        lows=(low, reclaim_low),
    )
    active = _record(pipeline, 110.0)
    assert active.lifecycle is LifecycleState.ACTIVE
    assert active.transition_cause == "RECLAIM_CONFIRMED"
    assert reclaimed.objective.nearest_high_price == 110.0
    causes = [
        item.cause
        for item in pipeline.structural_hierarchy.journal
        if item.swing_id == active.swing_id
    ]
    assert "PRICE_TRADE_THROUGH" in causes
    assert "RECLAIM_CONFIRMED" in causes


def test_liquidity_sweep_then_far_side_acceptance_confirms_broken() -> None:
    pipeline = ArchitecturePipeline(tick_size=TICK)
    high = _swing(110.0, 90.0, 1.0)
    low = _swing(90.0, 80.0, 1.5)
    _evaluate(
        pipeline,
        price=100.0,
        timestamp=10.0,
        highs=(high,),
        lows=(low,),
    )
    swept = _evaluate(
        pipeline,
        price=89.75,
        timestamp=11.0,
        highs=(high,),
        lows=(low,),
    )
    assert _record(pipeline, 90.0).lifecycle is LifecycleState.CHALLENGED
    assert swept.objective.nearest_low_price == 90.0

    acceptance_high = _swing(89.5, 70.0, 3.0)
    broken = _evaluate(
        pipeline,
        price=89.75,
        timestamp=12.0,
        highs=(high, acceptance_high),
        lows=(low,),
    )
    terminal = _record(pipeline, 90.0)
    assert terminal.lifecycle is LifecycleState.CONFIRMED_BROKEN
    assert terminal.transition_cause == "FAR_SIDE_ACCEPTANCE_CONFIRMED"
    assert broken.objective.nearest_low_price is None
    assert broken.objective.low_state is ObjectivePersistenceState.BREACHED


def test_governing_hierarchy_replacement_supersedes_active_objective() -> None:
    pipeline = ArchitecturePipeline(tick_size=TICK)
    high = _swing(110.0, 90.0, 1.0)
    old_low = _swing(90.0, 80.0, 1.5)
    _evaluate(
        pipeline,
        price=100.0,
        timestamp=10.0,
        highs=(high,),
        lows=(old_low,),
    )

    new_root_low = _swing(89.75, 85.0, 2.0)
    replaced = _evaluate(
        pipeline,
        price=100.0,
        timestamp=11.0,
        highs=(high,),
        lows=(old_low, new_root_low),
    )
    old = _record(pipeline, 90.0)
    assert old.lifecycle is LifecycleState.SUPERSEDED
    assert old.transition_cause == "HIERARCHY_GOVERNING_REPLACEMENT"
    assert replaced.objective.nearest_low_price == 89.75
    assert replaced.objective.low_state is ObjectivePersistenceState.SUPERSEDED


def test_archive_requires_terminal_state_and_epoch_closing_root() -> None:
    hierarchy = PersistentStructuralHierarchy()
    old_low = _swing(90.0, 80.0, 1.0)
    high = _swing(110.0, 90.0, 1.5)
    hierarchy.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(high,),
            confirmed_lows=(old_low,),
            timestamp=10.0,
        )
    )
    old_id = next(r.swing_id for r in hierarchy.snapshot().records if r.price == 90.0)
    with pytest.raises(ValueError, match="terminal"):
        hierarchy.archive(old_id, timestamp=10.5)

    new_root = _swing(89.75, 85.0, 2.0)
    hierarchy.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(high,),
            confirmed_lows=(old_low, new_root),
            timestamp=11.0,
        )
    )
    new_id = next(
        r.swing_id for r in hierarchy.snapshot().records if r.price == 89.75
    )
    with pytest.raises(ValueError, match="epoch_closing"):
        hierarchy.archive(old_id, timestamp=11.5)
    hierarchy.archive(
        old_id,
        timestamp=12.0,
        evidence={"epoch_closing_swing_id": new_id},
    )
    archived = next(r for r in hierarchy.snapshot().records if r.swing_id == old_id)
    assert archived.lifecycle is LifecycleState.ARCHIVED
    assert archived.transition_cause == "STRUCTURAL_EPOCH_CLOSED"


def test_challenged_restart_continuity_and_resolution(tmp_path: Path) -> None:
    checkpoint = tmp_path / "h4-hierarchy.json"
    high = _swing(110.0, 90.0, 1.0)
    low = _swing(90.0, 80.0, 1.5)
    original = PersistentStructuralHierarchy(checkpoint_path=checkpoint)
    original.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=TICK,
            confirmed_highs=(high,),
            confirmed_lows=(low,),
            timestamp=10.0,
        )
    )
    original.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=89.75,
            tick_size=TICK,
            confirmed_highs=(high,),
            confirmed_lows=(low,),
            timestamp=11.0,
        )
    )

    restored = PersistentStructuralHierarchy(checkpoint_path=checkpoint)
    assert restored.snapshot() == original.snapshot()
    assert restored.journal == original.journal
    restored.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=89.75,
            tick_size=TICK,
            confirmed_highs=(high, _swing(89.5, 70.0, 3.0)),
            confirmed_lows=(low,),
            timestamp=12.0,
        )
    )
    restored_low = next(r for r in restored.snapshot().records if r.price == 90.0)
    assert restored_low.lifecycle is LifecycleState.CONFIRMED_BROKEN


def test_challenge_replay_is_deterministic() -> None:
    high = _swing(110.0, 90.0, 1.0)
    low = _swing(90.0, 80.0, 1.5)
    reclaim = _swing(109.0, 65.0, 3.0)
    events = (
        ObjectiveDiagnosticsInputs(100.0, TICK, (high,), (low,), 10.0),
        ObjectiveDiagnosticsInputs(110.25, TICK, (high,), (low,), 11.0),
        ObjectiveDiagnosticsInputs(109.5, TICK, (high,), (low, reclaim), 12.0),
    )
    left = PersistentStructuralHierarchy()
    right = PersistentStructuralHierarchy()
    for event in events:
        left.evaluate(event)
        right.evaluate(event)
    assert left.snapshot() == right.snapshot()
    assert left.journal == right.journal


def test_developer_view_exposes_lifecycle_challenge_and_transition_evidence() -> None:
    pipeline = ArchitecturePipeline(tick_size=TICK)
    high = _swing(110.0, 90.0, 1.0)
    low = _swing(90.0, 80.0, 1.5)
    _evaluate(
        pipeline,
        price=100.0,
        timestamp=10.0,
        highs=(high,),
        lows=(low,),
    )
    frame = _evaluate(
        pipeline,
        price=110.25,
        timestamp=11.0,
        highs=(high,),
        lows=(low,),
    )
    report = pipeline.audit_objectives(
        ObjectiveDiagnosticsInputs(110.25, TICK, (high,), (low,), 11.0)
    )
    text = render_validator_frame(
        replace(frame, objective_diagnostics=report),
        developer_mode=True,
    )
    assert "Lifecycle        CHALLENGED" in text
    assert "Challenge State  UNDER_CHALLENGE" in text
    assert "Challenge Evidence" in text
    assert "Transition Cause PRICE_TRADE_THROUGH" in text
    assert "Transition Time" in text
