"""H-2 contract tests for persistent structural hierarchy."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.objective import ConfirmedSwing
from hotirjam_ai5.objective_diagnostics import (
    CandidateCategory,
    LifecycleState,
    ObjectiveAuditReport,
    ObjectiveDiagnosticsInputs,
    PersistentStructuralHierarchy,
)


TICK = 0.25


def _swing(price: float, strength: float, at: float) -> ConfirmedSwing:
    return ConfirmedSwing(price=price, strength=strength, confirmed_at=at)


def _inputs(
    *,
    price: float = 100.0,
    highs: tuple[ConfirmedSwing, ...] = (),
    lows: tuple[ConfirmedSwing, ...] = (),
    timestamp: float = 10.0,
) -> ObjectiveDiagnosticsInputs:
    return ObjectiveDiagnosticsInputs(
        current_price=price,
        tick_size=TICK,
        confirmed_highs=highs,
        confirmed_lows=lows,
        timestamp=timestamp,
    )


def _record_at(
    hierarchy: PersistentStructuralHierarchy, price: float
):
    return next(r for r in hierarchy.snapshot().records if r.price == price)


def test_ids_parents_depth_and_category_survive_buffer_eviction() -> None:
    hierarchy = PersistentStructuralHierarchy()
    parent = _swing(110.0, 90.0, 1.0)
    child = _swing(105.0, 70.0, 2.0)
    low = _swing(90.0, 80.0, 1.5)

    hierarchy.evaluate(_inputs(highs=(parent, child), lows=(low,)))
    before_parent = _record_at(hierarchy, 110.0)
    before_child = _record_at(hierarchy, 105.0)
    before_version = hierarchy.hierarchy_version
    before_transitions = len(hierarchy.journal)

    report = hierarchy.evaluate(
        _inputs(highs=(child,), lows=(low,), timestamp=11.0)
    )
    after_parent = _record_at(hierarchy, 110.0)
    after_child = _record_at(hierarchy, 105.0)

    assert after_parent.swing_id == before_parent.swing_id
    assert after_child.swing_id == before_child.swing_id
    assert after_child.parent_id == before_parent.swing_id
    assert after_child.depth == before_child.depth == 1
    assert after_child.category is before_child.category is CandidateCategory.MINOR
    assert hierarchy.hierarchy_version == before_version
    assert len(hierarchy.journal) == before_transitions
    assert {item.price for item in report.highs} == {105.0, 110.0}


def test_repeated_input_does_not_regenerate_ids_or_mutate_hierarchy() -> None:
    hierarchy = PersistentStructuralHierarchy()
    inputs = _inputs(
        highs=(_swing(110.0, 90.0, 1.0),),
        lows=(_swing(90.0, 80.0, 1.5),),
    )
    first = hierarchy.evaluate(inputs)
    first_snapshot = hierarchy.snapshot()
    second = hierarchy.evaluate(inputs)

    assert hierarchy.snapshot() == first_snapshot
    assert [d.swing_id for d in first.highs] == [d.swing_id for d in second.highs]
    assert [d.swing_id for d in first.lows] == [d.swing_id for d in second.lows]


def test_replay_is_deterministic() -> None:
    events = (
        _inputs(
            highs=(_swing(110.0, 90.0, 1.0),),
            lows=(_swing(90.0, 80.0, 1.5),),
            timestamp=10.0,
        ),
        _inputs(
            price=100.0,
            highs=(
                _swing(110.0, 90.0, 1.0),
                _swing(105.0, 70.0, 2.0),
            ),
            lows=(_swing(90.0, 80.0, 1.5),),
            timestamp=11.0,
        ),
    )
    left = PersistentStructuralHierarchy()
    right = PersistentStructuralHierarchy()
    for event in events:
        left.evaluate(event)
        right.evaluate(event)

    assert left.snapshot() == right.snapshot()
    assert left.journal == right.journal


def test_checkpoint_restart_continuity(tmp_path: Path) -> None:
    checkpoint = tmp_path / "hierarchy.json"
    original = PersistentStructuralHierarchy(checkpoint_path=checkpoint)
    inputs = _inputs(
        highs=(
            _swing(110.0, 90.0, 1.0),
            _swing(105.0, 70.0, 2.0),
        ),
        lows=(_swing(90.0, 80.0, 1.5),),
    )
    original.evaluate(inputs)

    restored = PersistentStructuralHierarchy(checkpoint_path=checkpoint)
    assert restored.snapshot() == original.snapshot()
    assert restored.journal == original.journal

    version = restored.hierarchy_version
    restored.evaluate(inputs)
    assert restored.hierarchy_version == version


def test_archived_parent_remains_structural_anchor() -> None:
    hierarchy = PersistentStructuralHierarchy()
    parent = _swing(110.0, 90.0, 1.0)
    child = _swing(105.0, 70.0, 2.0)
    low = _swing(90.0, 80.0, 1.5)
    hierarchy.evaluate(_inputs(highs=(parent, child), lows=(low,)))
    parent_id = _record_at(hierarchy, 110.0).swing_id

    hierarchy.evaluate(
        _inputs(
            price=111.0,
            highs=(parent, child),
            lows=(low,),
            timestamp=12.0,
        )
    )
    hierarchy.archive(
        parent_id,
        timestamp=13.0,
        evidence={"reason": "terminal-history-compaction"},
    )

    archived_parent = _record_at(hierarchy, 110.0)
    retained_child = _record_at(hierarchy, 105.0)
    assert archived_parent.lifecycle is LifecycleState.ARCHIVED
    assert retained_child.parent_id == archived_parent.swing_id
    assert retained_child.depth == 1
    assert retained_child.category is CandidateCategory.MINOR


def test_transition_journal_records_old_new_state_and_evidence() -> None:
    hierarchy = PersistentStructuralHierarchy()
    high = _swing(110.0, 90.0, 1.0)
    low = _swing(90.0, 80.0, 1.5)
    hierarchy.evaluate(_inputs(highs=(high,), lows=(low,), timestamp=10.0))
    high_id = _record_at(hierarchy, 110.0).swing_id

    hierarchy.evaluate(
        _inputs(
            price=111.0,
            highs=(high,),
            lows=(low,),
            timestamp=11.0,
        )
    )
    transition = hierarchy.journal[-1]
    assert transition.cause == "PRICE_BREACH"
    assert transition.swing_id == high_id
    assert transition.timestamp == 11.0
    assert transition.old_state is not None
    assert transition.new_state is not None
    assert transition.old_state["lifecycle"] == "ACTIVE"
    assert transition.new_state["lifecycle"] == "BREACHED"
    assert transition.evidence["current_price"] == 111.0


def test_supersession_is_event_driven_and_journaled() -> None:
    hierarchy = PersistentStructuralHierarchy()
    early = _swing(108.0, 60.0, 1.0)
    later = _swing(108.25, 65.0, 2.0)
    low = _swing(90.0, 80.0, 1.5)
    hierarchy.evaluate(_inputs(highs=(early,), lows=(low,), timestamp=10.0))
    hierarchy.evaluate(
        _inputs(highs=(early, later), lows=(low,), timestamp=11.0)
    )

    early_record = _record_at(hierarchy, 108.0)
    transition = next(
        item
        for item in hierarchy.journal
        if item.swing_id == early_record.swing_id
        and item.cause == "SWING_SUPERSEDED"
    )
    assert early_record.lifecycle is LifecycleState.SUPERSEDED
    assert transition.evidence["superseding_swing_id"] == _record_at(
        hierarchy, 108.25
    ).swing_id


def test_adapter_preserves_objective_audit_report_interface() -> None:
    hierarchy = PersistentStructuralHierarchy()
    report = hierarchy.evaluate(
        _inputs(
            highs=(_swing(110.0, 90.0, 1.0),),
            lows=(_swing(90.0, 80.0, 1.5),),
        )
    )
    assert isinstance(report, ObjectiveAuditReport)
    assert report.hierarchy_version == hierarchy.hierarchy_version
    assert report.registry_size == 2
    assert report.transition_count == len(hierarchy.journal)
    assert report.checkpoint_version == 1


def test_pipeline_objective_unchanged_when_parent_leaves_rolling_input() -> None:
    pipeline = ArchitecturePipeline(tick_size=TICK)
    parent = _swing(110.0, 90.0, 1.0)
    child = _swing(105.0, 70.0, 2.0)
    low = _swing(90.0, 80.0, 1.5)

    first = pipeline.evaluate(
        current_price=100.0,
        timestamp=10.0,
        candles=(),
        confirmed_highs=(parent, child),
        confirmed_lows=(low,),
    )
    version = pipeline.structural_hierarchy.hierarchy_version
    second = pipeline.evaluate(
        current_price=100.0,
        timestamp=11.0,
        candles=(),
        confirmed_highs=(child,),
        confirmed_lows=(low,),
    )

    assert first.objective.nearest_high_price == 110.0
    assert second.objective.nearest_high_price == 110.0
    assert pipeline.structural_hierarchy.hierarchy_version == version
    retained = _record_at(pipeline.structural_hierarchy, 105.0)
    assert retained.category is CandidateCategory.MINOR
    assert retained.depth == 1


def test_exact_29309_parent_eviction_cannot_promote_29303() -> None:
    hierarchy = PersistentStructuralHierarchy()
    parent = _swing(29309.0, 90.0, 1.0)
    child = _swing(29303.0, 75.0, 2.0)
    low = _swing(29280.0, 90.0, 1.5)
    hierarchy.evaluate(
        _inputs(
            price=29295.0,
            highs=(parent, child),
            lows=(low,),
            timestamp=10.0,
        )
    )
    before = _record_at(hierarchy, 29303.0)

    report = hierarchy.evaluate(
        _inputs(
            price=29295.0,
            highs=(child,),
            lows=(low,),
            timestamp=11.0,
        )
    )
    after = _record_at(hierarchy, 29303.0)
    diagnostic = next(item for item in report.highs if item.price == 29303.0)

    assert after.swing_id == before.swing_id
    assert after.parent_id == _record_at(hierarchy, 29309.0).swing_id
    assert after.depth == before.depth == 1
    assert after.category is before.category is CandidateCategory.MINOR
    assert diagnostic.eligible is False
