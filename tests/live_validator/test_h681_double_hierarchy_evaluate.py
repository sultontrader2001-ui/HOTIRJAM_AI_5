"""H-6.8.1 probe still works; H-6.8.2 removed the second evaluate.

After Alternative 1, every accepted tick must show exactly one
PersistentStructuralHierarchy.evaluate().
"""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import LiveValidatorController
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.objective_diagnostics.hierarchy_evaluate_probe import (
    build_hierarchy_evaluate_probe_stats,
    hierarchy_evaluate_call_records,
    hierarchy_evaluate_pair_comparisons,
    render_hierarchy_evaluate_probe_report,
    reset_hierarchy_evaluate_probe_for_tests,
)


def _tick(price: float, *, ts: float) -> LiveTick:
    return LiveTick(
        timestamp=ts,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=1.0,
    )


def test_h681_probe_confirms_single_evaluate_after_h682(tmp_path: Path) -> None:
    reset_hierarchy_evaluate_probe_for_tests()
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "hierarchy.json",
            initiative_checkpoint_path=tmp_path / "initiative.json",
        )
    )
    for i in range(1, 6):
        controller.on_tick(_tick(100.0 + i * 0.25, ts=float(i)))

    stats = build_hierarchy_evaluate_probe_stats()
    records = hierarchy_evaluate_call_records()
    comparisons = hierarchy_evaluate_pair_comparisons()
    report = render_hierarchy_evaluate_probe_report(stats)

    assert stats.accepted_ticks == 5
    assert stats.hierarchy_evaluations == 5
    assert stats.average_evaluations_per_tick == 1.0
    assert stats.maximum_evaluations_per_tick == 1
    assert stats.minimum_evaluations_per_tick == 1
    assert stats.distribution.get(1) == 5
    assert stats.ticks_with_multiple_evaluations == 0
    assert comparisons == ()
    assert "Maximum evaluations per tick.. 1" in report

    for tick_id in range(1, 6):
        tick_calls = [r for r in records if r.tick_id == tick_id]
        assert len(tick_calls) == 1
        assert tick_calls[0].call_number == 1
        assert "objective_engine.py" in tick_calls[0].caller or any(
            "objective_engine.py:" in line for line in tick_calls[0].call_stack
        )


def test_h681_probe_does_not_run_without_accepted_tick_context() -> None:
    """Direct hierarchy.evaluate without Tick ID still records unbound calls."""
    reset_hierarchy_evaluate_probe_for_tests()
    from hotirjam_ai5.objective import ConfirmedSwing
    from hotirjam_ai5.objective_diagnostics import (
        ObjectiveDiagnosticsInputs,
        PersistentStructuralHierarchy,
    )

    h = PersistentStructuralHierarchy()
    h.evaluate(
        ObjectiveDiagnosticsInputs(
            current_price=100.0,
            tick_size=0.25,
            confirmed_highs=(ConfirmedSwing(price=110.0, strength=80.0, confirmed_at=1.0),),
            confirmed_lows=(ConfirmedSwing(price=90.0, strength=80.0, confirmed_at=1.0),),
            timestamp=1.0,
        )
    )
    stats = build_hierarchy_evaluate_probe_stats()
    assert stats.accepted_ticks == 0
    assert stats.hierarchy_evaluations == 1
    assert stats.verdict == "REJECTED"
    rec = hierarchy_evaluate_call_records()[0]
    assert rec.tick_id is None
