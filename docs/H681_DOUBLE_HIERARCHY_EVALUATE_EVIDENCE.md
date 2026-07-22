# Sprint H-6.8.1 — Double Hierarchy.evaluate Evidence

**VERDICT: CONFIRMED**

Instrumentation only. No behavior / API / persistence / output changes.

## Method

- Tick ID assigned in `LiveValidatorController.on_tick` via `hierarchy_accepted_tick()`.
- Every `PersistentStructuralHierarchy.evaluate()` records call metadata via probe.
- `checkpoint()` notes writes for the active Tick ID.
- Evidence harness: Live Validator accepted-tick path (unit + scripted runs).
- Suite: **565 passed**.

## Statistics (10 quiet ticks)

| Metric | Value |
|--------|------:|
| Accepted ticks | 10 |
| Hierarchy evaluations | 20 |
| Average evaluations per tick | 2.0000 |
| Maximum evaluations per tick | 2 |
| Minimum evaluations per tick | 2 |
| Distribution | 2 → 10 ticks |

## Statistics (5 ticks with seeded swings / penetration)

| Metric | Value |
|--------|------:|
| Accepted ticks | 5 |
| Hierarchy evaluations | 10 |
| Average / max / min per tick | 2 / 2 / 2 |
| Verdict | CONFIRMED |

## Call pattern (every accepted tick)

| Call # | Caller | Role |
|--------|--------|------|
| 1 | `objective_engine.py:_evaluate_structural_candidates` → `audit_objectives` | Objective selection |
| 2 | `pipeline.py:audit_objectives` from `controller.py:_evaluate` | Attach `objective_diagnostics` |

## Pair comparison summary

| Dimension | Quiet ticks | Active/challenge ticks |
|-----------|-------------|------------------------|
| Input | IDENTICAL | IDENTICAL |
| Output | IDENTICAL | IDENTICAL (report after call 1 already final) |
| Mutation | IDENTICAL (neither mutates when empty) | PARTIAL (call 1 mutates; call 2 no-op) |
| Checkpoint | IDENTICAL (false/false) | DIFFERENT (call 1 may write; call 2 does not) |
| Journal / Version | IDENTICAL when quiet | PARTIAL when call 1 transitions |
| Overall | IDENTICAL | PARTIAL |

## Why the second evaluation exists

**Classification: Presentation only**

After `ArchitecturePipeline.evaluate()` completes Objective selection (which already
calls `audit_objectives` → `hierarchy.evaluate`), `LiveValidatorController._evaluate()`
calls `pipeline.audit_objectives()` again to attach `objective_diagnostics` onto
`ValidatorFrame`. That second path re-enters `PersistentStructuralHierarchy.evaluate()`.

Controller comment claims this does not re-evaluate hierarchy; probe proves it does
re-enter full mutating `evaluate()` (even when the second call is often a no-op
mutation after the first call already applied challenges).

## Sample Tick ID 1 (seeded swings, price 98.5)

### Call 1 — Objective path
- Caller: `objective_engine.py:_evaluate_structural_candidates`
- State mutated: True
- Version: 0 → 5
- Journal changed: True
- Checkpoint written: True
- Records added: 2
- Challenges applied: True

### Call 2 — Presentation path
- Caller: `pipeline.py:audit_objectives`
- State mutated: False
- Version: 5 → 5
- Journal changed: False
- Checkpoint written: False
- Records added: 0
- Challenges applied: False
- Input: IDENTICAL to call 1

## Final verdict

# CONFIRMED

`PersistentStructuralHierarchy.evaluate()` executes **exactly twice** for every
accepted Live Validator tick under the current architecture.
