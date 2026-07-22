"""H-6.8.1 — Hierarchy evaluate probe (instrumentation only).

Records every PersistentStructuralHierarchy.evaluate() call against an
accepted-tick ID. Never changes evaluate semantics, outputs, or persistence.
Instrumentation failures are ignored.
"""

from __future__ import annotations

import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterator, Mapping

_tick_id: ContextVar[int | None] = ContextVar("h681_tick_id", default=None)
_tick_call_count: ContextVar[int] = ContextVar("h681_tick_call_count", default=0)
_checkpoint_note: ContextVar[bool] = ContextVar("h681_checkpoint_note", default=False)

_next_tick_id = 0
_enabled = True
_records: list[HierarchyEvaluateCallRecord] = []
_comparisons: list[HierarchyEvaluatePairComparison] = []
_accepted_ticks = 0


class PairRelation(StrEnum):
    IDENTICAL = "IDENTICAL"
    DIFFERENT = "DIFFERENT"
    PARTIAL = "PARTIAL"


class SecondCallClassification(StrEnum):
    REQUIRED = "Required"
    PRESENTATION_ONLY = "Presentation only"
    LEGACY = "Legacy"
    BUG = "Bug"
    UNKNOWN = "Unknown"


@dataclass(frozen=True, slots=True)
class HierarchyEvaluateCallRecord:
    tick_id: int | None
    call_number: int
    caller: str
    call_stack: tuple[str, ...]
    timestamp: float
    duration_ms: float
    input_summary: Mapping[str, Any]
    output_summary: Mapping[str, Any]
    state_mutated: bool
    version_changed: bool
    journal_changed: bool
    checkpoint_written: bool
    records_added: int
    challenges_applied: bool
    reasons_changed: bool
    version_before: int
    version_after: int
    journal_len_before: int
    journal_len_after: int
    registry_before: int
    registry_after: int


@dataclass(frozen=True, slots=True)
class HierarchyEvaluatePairComparison:
    tick_id: int
    first_call_number: int
    second_call_number: int
    input_relation: PairRelation
    output_relation: PairRelation
    mutation_relation: PairRelation
    checkpoint_relation: PairRelation
    journal_relation: PairRelation
    version_relation: PairRelation
    overall: PairRelation
    first_caller: str
    second_caller: str
    second_classification: SecondCallClassification
    why_second_exists: str


@dataclass
class HierarchyEvaluateProbeStats:
    accepted_ticks: int = 0
    hierarchy_evaluations: int = 0
    average_evaluations_per_tick: float = 0.0
    maximum_evaluations_per_tick: int = 0
    minimum_evaluations_per_tick: int = 0
    distribution: dict[int, int] = field(default_factory=dict)
    ticks_with_multiple_evaluations: int = 0
    comparisons: tuple[HierarchyEvaluatePairComparison, ...] = ()
    verdict: str = "REJECTED"
    second_call_why: str | None = None
    second_call_classification: SecondCallClassification | None = None


def reset_hierarchy_evaluate_probe_for_tests() -> None:
    """Clear probe state (tests / evidence harness)."""
    global _next_tick_id, _accepted_ticks, _records, _comparisons, _enabled
    _next_tick_id = 0
    _accepted_ticks = 0
    _records = []
    _comparisons = []
    _enabled = True
    _tick_id.set(None)
    _tick_call_count.set(0)
    _checkpoint_note.set(False)


def set_hierarchy_evaluate_probe_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)


def current_hierarchy_tick_id() -> int | None:
    return _tick_id.get()


def note_hierarchy_checkpoint_write() -> None:
    """Called from checkpoint() — diagnostics only."""
    try:
        if not _enabled:
            return
        if _tick_id.get() is None:
            return
        _checkpoint_note.set(True)
    except Exception:
        return


@contextmanager
def hierarchy_accepted_tick() -> Iterator[int]:
    """Assign a Tick ID for one accepted tick; clear afterward."""
    global _next_tick_id, _accepted_ticks
    if not _enabled:
        yield -1
        return
    _next_tick_id += 1
    tick = _next_tick_id
    token = _tick_id.set(tick)
    count_token = _tick_call_count.set(0)
    ck_token = _checkpoint_note.set(False)
    _accepted_ticks += 1
    try:
        yield tick
    finally:
        try:
            # After tick completes, compare multi-eval pairs for this tick.
            _finalize_tick_comparisons(tick)
        except Exception:
            pass
        _tick_id.reset(token)
        _tick_call_count.reset(count_token)
        _checkpoint_note.reset(ck_token)


def hierarchy_evaluate_call_records() -> tuple[HierarchyEvaluateCallRecord, ...]:
    return tuple(_records)


def hierarchy_evaluate_pair_comparisons() -> tuple[HierarchyEvaluatePairComparison, ...]:
    return tuple(_comparisons)


def _caller_and_stack() -> tuple[str, tuple[str, ...]]:
    frames = traceback.extract_stack(limit=40)
    # Drop this helper and evaluate/probe frames from the top of the useful stack.
    useful: list[str] = []
    caller = "unknown"
    for fr in frames:
        name = fr.name
        filename = fr.filename.replace("\\", "/")
        short = filename.rsplit("/", 1)[-1]
        if name in {
            "_caller_and_stack",
            "begin_hierarchy_evaluate_probe",
            "finish_hierarchy_evaluate_probe",
            "evaluate",
            "hierarchy_accepted_tick",
            "__enter__",
            "__exit__",
        }:
            continue
        if short.endswith("hierarchy_evaluate_probe.py"):
            continue
        line = f"{short}:{fr.lineno}:{name}"
        useful.append(line)
    # Prefer frames closest to hierarchy.evaluate (most specific first).
    ranked = (
        ("objective_engine.py", "_evaluate_structural_candidates"),
        ("objective_engine.py", "evaluate"),
        ("pipeline.py", "audit_objectives"),
        ("objective_audit.py", "audit_objectives"),
        ("pipeline.py", "evaluate"),
        ("controller.py", "_evaluate"),
        ("controller.py", "on_tick"),
    )
    for short, name in ranked:
        for line in reversed(useful):
            if line.startswith(f"{short}:") and line.endswith(f":{name}"):
                caller = f"{short}:{name}"
                return caller, tuple(useful[-16:])
    if useful:
        caller = useful[-1]
    return caller, tuple(useful[-16:])


def _input_summary(inputs: Any) -> dict[str, Any]:
    try:
        highs = getattr(inputs, "confirmed_highs", ()) or ()
        lows = getattr(inputs, "confirmed_lows", ()) or ()
        return {
            "current_price": getattr(inputs, "current_price", None),
            "tick_size": getattr(inputs, "tick_size", None),
            "timestamp": getattr(inputs, "timestamp", None),
            "high_count": len(highs),
            "low_count": len(lows),
            "high_prices": tuple(float(s.price) for s in highs[:8]),
            "low_prices": tuple(float(s.price) for s in lows[:8]),
            "session_high": getattr(inputs, "session_high", None),
            "session_low": getattr(inputs, "session_low", None),
        }
    except Exception:
        return {}


def _output_summary(report: Any | None) -> dict[str, Any]:
    if report is None:
        return {}
    try:
        highs = getattr(report, "highs", ()) or ()
        lows = getattr(report, "lows", ()) or ()

        def _side_brief(items: tuple[Any, ...]) -> tuple[dict[str, Any], ...]:
            out: list[dict[str, Any]] = []
            for item in items[:8]:
                out.append(
                    {
                        "swing_id": getattr(item, "swing_id", None),
                        "price": getattr(item, "price", None),
                        "lifecycle": str(getattr(item, "lifecycle", "")),
                        "eligible": getattr(item, "eligible", None),
                        "rejection_reasons": tuple(
                            getattr(item, "rejection_reasons", ()) or ()
                        ),
                        "challenge_state": getattr(item, "challenge_state", None),
                    }
                )
            return tuple(out)

        return {
            "hierarchy_version": getattr(report, "hierarchy_version", None),
            "registry_size": getattr(report, "registry_size", None),
            "transition_count": getattr(report, "transition_count", None),
            "high_count": len(highs),
            "low_count": len(lows),
            "summary_lines": tuple(getattr(report, "summary_lines", ()) or ())[:12],
            "highs": _side_brief(tuple(highs)),
            "lows": _side_brief(tuple(lows)),
        }
    except Exception:
        return {}


def _challenge_fingerprint(hierarchy: Any) -> tuple[tuple[Any, ...], ...]:
    try:
        rows: list[tuple[Any, ...]] = []
        for sid in sorted(hierarchy._records):
            rec = hierarchy._records[sid]
            rows.append(
                (
                    sid,
                    str(rec.lifecycle),
                    rec.challenge_started_at,
                    rec.challenge_extreme_price,
                    tuple(rec.challenge_evidence),
                )
            )
        return tuple(rows)
    except Exception:
        return ()


def _reasons_fingerprint(report: Any | None) -> tuple[Any, ...]:
    if report is None:
        return ()
    try:
        rows: list[Any] = []
        for side in (getattr(report, "highs", ()), getattr(report, "lows", ())):
            for item in side or ():
                rows.append(
                    (
                        getattr(item, "swing_id", None),
                        tuple(getattr(item, "rejection_reasons", ()) or ()),
                        getattr(item, "challenge_state", None),
                        tuple(getattr(item, "challenge_evidence", ()) or ()),
                    )
                )
        rows.append(tuple(getattr(report, "summary_lines", ()) or ()))
        return tuple(rows)
    except Exception:
        return ()


@dataclass
class _ActiveProbe:
    tick_id: int | None
    call_number: int
    caller: str
    call_stack: tuple[str, ...]
    timestamp: float
    started: float
    input_summary: dict[str, Any]
    version_before: int
    journal_len_before: int
    registry_before: int
    challenge_before: tuple[tuple[Any, ...], ...]
    reasons_before: tuple[Any, ...] = ()


def begin_hierarchy_evaluate_probe(hierarchy: Any, inputs: Any) -> _ActiveProbe | None:
    """Start exclusive timing/state capture for one evaluate() call."""
    import time

    try:
        if not _enabled:
            return None
        tick = _tick_id.get()
        call_number = _tick_call_count.get() + 1
        _tick_call_count.set(call_number)
        _checkpoint_note.set(False)
        caller, stack = _caller_and_stack()
        return _ActiveProbe(
            tick_id=tick,
            call_number=call_number,
            caller=caller,
            call_stack=stack,
            timestamp=time.time(),
            started=time.perf_counter(),
            input_summary=_input_summary(inputs),
            version_before=int(getattr(hierarchy, "_version", 0)),
            journal_len_before=len(getattr(hierarchy, "_journal", ()) or ()),
            registry_before=len(getattr(hierarchy, "_records", {}) or {}),
            challenge_before=_challenge_fingerprint(hierarchy),
        )
    except Exception:
        return None


def finish_hierarchy_evaluate_probe(
    probe: _ActiveProbe | None,
    hierarchy: Any,
    report: Any | None,
) -> None:
    """Seal one evaluate() probe record. Never raises into evaluate()."""
    import time

    try:
        if probe is None or not _enabled:
            return
        duration_ms = (time.perf_counter() - probe.started) * 1000.0
        version_after = int(getattr(hierarchy, "_version", 0))
        journal_len_after = len(getattr(hierarchy, "_journal", ()) or ())
        registry_after = len(getattr(hierarchy, "_records", {}) or {})
        challenge_after = _challenge_fingerprint(hierarchy)
        output = _output_summary(report)
        reasons_after = _reasons_fingerprint(report)
        version_changed = version_after != probe.version_before
        journal_changed = journal_len_after != probe.journal_len_before
        records_added = max(0, registry_after - probe.registry_before)
        challenges_applied = challenge_after != probe.challenge_before
        # "Reasons changed" vs pre-call: compare report reasons to empty baseline
        # only when we have a prior report on this tick; otherwise use challenge/
        # rejection fingerprint vs empty for call #1 (always "changed" if any).
        reasons_changed = False
        prior = [
            r
            for r in _records
            if r.tick_id is not None
            and r.tick_id == probe.tick_id
            and r.call_number < probe.call_number
        ]
        if prior:
            reasons_changed = reasons_after != _reasons_fingerprint_from_output(
                prior[-1].output_summary
            )
        else:
            reasons_changed = bool(reasons_after)
        state_mutated = (
            version_changed
            or journal_changed
            or records_added > 0
            or challenges_applied
        )
        checkpoint_written = bool(_checkpoint_note.get())
        _records.append(
            HierarchyEvaluateCallRecord(
                tick_id=probe.tick_id,
                call_number=probe.call_number,
                caller=probe.caller,
                call_stack=probe.call_stack,
                timestamp=probe.timestamp,
                duration_ms=duration_ms,
                input_summary=dict(probe.input_summary),
                output_summary=dict(output),
                state_mutated=state_mutated,
                version_changed=version_changed,
                journal_changed=journal_changed,
                checkpoint_written=checkpoint_written,
                records_added=records_added,
                challenges_applied=challenges_applied,
                reasons_changed=reasons_changed,
                version_before=probe.version_before,
                version_after=version_after,
                journal_len_before=probe.journal_len_before,
                journal_len_after=journal_len_after,
                registry_before=probe.registry_before,
                registry_after=registry_after,
            )
        )
    except Exception:
        return


def _reasons_fingerprint_from_output(output: Mapping[str, Any]) -> tuple[Any, ...]:
    try:
        rows: list[Any] = []
        for side_key in ("highs", "lows"):
            for item in output.get(side_key, ()) or ():
                if not isinstance(item, Mapping):
                    continue
                rows.append(
                    (
                        item.get("swing_id"),
                        tuple(item.get("rejection_reasons") or ()),
                        item.get("challenge_state"),
                    )
                )
        rows.append(tuple(output.get("summary_lines") or ()))
        return tuple(rows)
    except Exception:
        return ()


def _relation(a: Any, b: Any) -> PairRelation:
    if a == b:
        return PairRelation.IDENTICAL
    # Partial: same shape/keys but differing values for mappings/tuples of maps.
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        if set(a.keys()) == set(b.keys()):
            return PairRelation.PARTIAL
    if isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b):
        return PairRelation.PARTIAL
    return PairRelation.DIFFERENT


def _mutation_signature(rec: HierarchyEvaluateCallRecord) -> tuple[Any, ...]:
    return (
        rec.state_mutated,
        rec.version_changed,
        rec.journal_changed,
        rec.records_added,
        rec.challenges_applied,
        rec.version_before,
        rec.version_after,
        rec.journal_len_before,
        rec.journal_len_after,
    )


def _classify_second_call(
    first: HierarchyEvaluateCallRecord,
    second: HierarchyEvaluateCallRecord,
) -> tuple[SecondCallClassification, str]:
    """Explain why a second evaluate exists for one Tick ID (evidence-based)."""
    first_from_objective = (
        "objective_engine.py" in first.caller
        or any("objective_engine.py:" in line for line in first.call_stack)
    )
    second_from_presentation = (
        second.caller == "pipeline.py:audit_objectives"
        or any(
            "pipeline.py:" in line and "audit_objectives" in line
            for line in second.call_stack
        )
        or (
            "controller.py:_evaluate" in second.caller
            and any(
                "pipeline.py:" in line and "audit_objectives" in line
                for line in second.call_stack
            )
        )
    )
    if first_from_objective and second_from_presentation:
        why = (
            "After ArchitecturePipeline.evaluate() completes Objective selection "
            "(which already calls audit_objectives → hierarchy.evaluate), "
            "LiveValidatorController._evaluate() calls pipeline.audit_objectives() "
            "again to attach objective_diagnostics onto ValidatorFrame. "
            "That second path re-enters PersistentStructuralHierarchy.evaluate()."
        )
        # Intent in controller comments is presentation-only attachment.
        return SecondCallClassification.PRESENTATION_ONLY, why
    if second_from_presentation:
        return (
            SecondCallClassification.PRESENTATION_ONLY,
            "Second call originates from LiveValidatorController._evaluate "
            "presentation diagnostics attachment (pipeline.audit_objectives).",
        )
    return (
        SecondCallClassification.UNKNOWN,
        f"Second caller={second.caller}; first caller={first.caller}.",
    )


def _finalize_tick_comparisons(tick_id: int) -> None:
    calls = [r for r in _records if r.tick_id == tick_id]
    if len(calls) < 2:
        return
    # Compare consecutive pairs (typically call 1 vs 2).
    for i in range(len(calls) - 1):
        a = calls[i]
        b = calls[i + 1]
        input_rel = _relation(a.input_summary, b.input_summary)
        output_rel = _relation(a.output_summary, b.output_summary)
        mut_rel = _relation(_mutation_signature(a), _mutation_signature(b))
        ck_rel = _relation(a.checkpoint_written, b.checkpoint_written)
        journal_rel = _relation(
            (a.journal_len_before, a.journal_len_after, a.journal_changed),
            (b.journal_len_before, b.journal_len_after, b.journal_changed),
        )
        version_rel = _relation(
            (a.version_before, a.version_after, a.version_changed),
            (b.version_before, b.version_after, b.version_changed),
        )
        relations = (
            input_rel,
            output_rel,
            mut_rel,
            ck_rel,
            journal_rel,
            version_rel,
        )
        if all(r is PairRelation.IDENTICAL for r in relations):
            overall = PairRelation.IDENTICAL
        elif any(r is PairRelation.DIFFERENT for r in relations) and any(
            r is PairRelation.IDENTICAL for r in relations
        ):
            overall = PairRelation.PARTIAL
        elif all(r is PairRelation.DIFFERENT for r in relations):
            overall = PairRelation.DIFFERENT
        else:
            overall = PairRelation.PARTIAL
        classification, why = _classify_second_call(a, b)
        _comparisons.append(
            HierarchyEvaluatePairComparison(
                tick_id=tick_id,
                first_call_number=a.call_number,
                second_call_number=b.call_number,
                input_relation=input_rel,
                output_relation=output_rel,
                mutation_relation=mut_rel,
                checkpoint_relation=ck_rel,
                journal_relation=journal_rel,
                version_relation=version_rel,
                overall=overall,
                first_caller=a.caller,
                second_caller=b.caller,
                second_classification=classification,
                why_second_exists=why,
            )
        )


def build_hierarchy_evaluate_probe_stats() -> HierarchyEvaluateProbeStats:
    """Aggregate probe records into H-6.8.1 statistics + verdict."""
    by_tick: dict[int, list[HierarchyEvaluateCallRecord]] = {}
    unbound = 0
    for rec in _records:
        if rec.tick_id is None:
            unbound += 1
            continue
        by_tick.setdefault(rec.tick_id, []).append(rec)

    counts = [len(v) for v in by_tick.values()] if by_tick else []
    distribution: dict[int, int] = {}
    for c in counts:
        distribution[c] = distribution.get(c, 0) + 1

    accepted = _accepted_ticks
    evaluations = len(_records)
    avg = (sum(counts) / len(counts)) if counts else 0.0
    maximum = max(counts) if counts else 0
    minimum = min(counts) if counts else 0
    multi = sum(1 for c in counts if c > 1)

    verdict = "REJECTED"
    if multi > 0 and multi == accepted and accepted > 0:
        verdict = "CONFIRMED"
    elif multi > 0:
        verdict = "PARTIALLY CONFIRMED"

    why = None
    classification = None
    if _comparisons:
        why = _comparisons[0].why_second_exists
        classification = _comparisons[0].second_classification

    return HierarchyEvaluateProbeStats(
        accepted_ticks=accepted,
        hierarchy_evaluations=evaluations,
        average_evaluations_per_tick=avg,
        maximum_evaluations_per_tick=maximum,
        minimum_evaluations_per_tick=minimum,
        distribution=dict(sorted(distribution.items())),
        ticks_with_multiple_evaluations=multi,
        comparisons=tuple(_comparisons),
        verdict=verdict,
        second_call_why=why,
        second_call_classification=classification,
    )


def render_hierarchy_evaluate_probe_report(
    stats: HierarchyEvaluateProbeStats | None = None,
) -> str:
    """Human-readable H-6.8.1 evidence report."""
    stats = stats or build_hierarchy_evaluate_probe_stats()
    lines = [
        "HOTIRJAM AI 5",
        "Sprint H-6.8.1 — Architecture Validation",
        "DOUBLE HIERARCHY.EVALUATE",
        "====================================================",
        "INSTRUMENTATION EVIDENCE REPORT",
        "====================================================",
        "",
        f"VERDICT: {stats.verdict}",
        "",
        "STATISTICS",
        f"  Accepted ticks................ {stats.accepted_ticks}",
        f"  Hierarchy evaluations......... {stats.hierarchy_evaluations}",
        f"  Average evaluations per tick.. {stats.average_evaluations_per_tick:.4f}",
        f"  Maximum evaluations per tick.. {stats.maximum_evaluations_per_tick}",
        f"  Minimum evaluations per tick.. {stats.minimum_evaluations_per_tick}",
        f"  Ticks with >1 evaluation...... {stats.ticks_with_multiple_evaluations}",
        "  Distribution (evals → ticks):",
    ]
    if stats.distribution:
        for k, v in stats.distribution.items():
            lines.append(f"    {k} → {v}")
    else:
        lines.append("    (none)")

    lines.extend(["", "PAIR COMPARISONS (ticks with ≥2 evaluates)"])
    if not stats.comparisons:
        lines.append("  (none)")
    else:
        for cmp in stats.comparisons[:20]:
            lines.extend(
                [
                    f"  Tick ID {cmp.tick_id}: call {cmp.first_call_number} vs {cmp.second_call_number}",
                    f"    First caller........... {cmp.first_caller}",
                    f"    Second caller.......... {cmp.second_caller}",
                    f"    Input.................. {cmp.input_relation.value}",
                    f"    Output................. {cmp.output_relation.value}",
                    f"    Mutation............... {cmp.mutation_relation.value}",
                    f"    Checkpoint............. {cmp.checkpoint_relation.value}",
                    f"    Journal................ {cmp.journal_relation.value}",
                    f"    Version................ {cmp.version_relation.value}",
                    f"    Overall................ {cmp.overall.value}",
                    f"    Second classification.. {cmp.second_classification.value}",
                ]
            )

    lines.extend(["", "WHY A SECOND EVALUATION EXISTS"])
    if stats.second_call_why:
        lines.append(f"  Classification: {stats.second_call_classification}")
        lines.append(f"  {stats.second_call_why}")
    else:
        lines.append("  N/A (no multi-evaluate ticks observed)")

    lines.extend(
        [
            "",
            "NOTES",
            "  - Probe is diagnostics-only; evaluate() behavior unchanged.",
            "  - Checkpoint written is observed via checkpoint() note flag.",
            "  - Tick IDs are assigned only inside hierarchy_accepted_tick().",
            "",
        ]
    )
    return "\n".join(lines)
