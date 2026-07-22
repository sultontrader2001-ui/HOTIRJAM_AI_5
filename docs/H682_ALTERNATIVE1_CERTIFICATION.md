# Sprint H-6.8.2 — Alternative 1 Certification Report

**Result: PASS**

## Architecture

### Old flow (H-6.8.1 CONFIRMED)
```
Tick ID
  → controller._evaluate
       → pipeline.evaluate
            → ObjectiveEngine.evaluate
                 → audit_objectives → hierarchy.evaluate   # #1 mutate
            → Initiative / Response / Continuation / Break
            → ValidatorFrame (diagnostics=None)
       → pipeline.audit_objectives → hierarchy.evaluate   # #2 redundant
       → rebuild ValidatorFrame(objective_diagnostics=report#2)
       → SnapshotLogger / IDC
```
**Evals/tick: 2**

### New flow (Alternative 1)
```
Tick ID
  → controller._evaluate
       → pipeline.evaluate
            → ObjectiveEngine.evaluate
                 → audit_objectives → hierarchy.evaluate   # ONLY mutate
                 → stash last_audit_report (exact instance)
            → Initiative / Response / Continuation / Break
            → ValidatorFrame(objective_diagnostics=last_audit_report)
       → SnapshotLogger / IDC  (same instance)
```
**Evals/tick: 1**

### Single source of truth
```
Hierarchy → ObjectiveAuditReport → Objective Engine → ValidatorFrame
         → Snapshot Logger → IDC
```
Same report **instance** (`is` identity) flows through.

## Certification evidence

| Check | Result |
|-------|--------|
| Max `hierarchy.evaluate` / Tick ID | **1** |
| Avg evaluations / tick | **1.0** |
| Report identity (engine ≡ frame) | **PASS** (`is`) |
| Fingerprint engine ≡ frame ≡ logger | **PASS** |
| Suite | **568 passed** |
| Checkpoint rule | Unchanged (version-gated inside single evaluate) |
| Second presentation evaluate | **Removed** |

### Before vs After (20 quiet ticks, no logger)

| Metric | Before | After |
|--------|-------:|------:|
| Hierarchy evaluations | 40 | 20 |
| Avg / tick | 2.0 | 1.0 |
| Max / tick | 2 | 1 |

### After (20 ticks + SnapshotLogger + checkpoints)

| Metric | Value |
|--------|------:|
| Hierarchy evals | 20 (avg 1.0) |
| Wall (20 on_tick) | ~8.8 ms |
| logging_ms (last sample) | ~1.2 ms |
| checkpoint_ms (last sample) | ~3.6 ms |

Hierarchy CPU for the redundant second evaluate is eliminated (~50% of hierarchy.evaluate call count).

## Files touched (Alt 1 only)

- `objective/objective_engine.py` — `last_audit_report` stash
- `live_validator/pipeline.py` — attach report to frame
- `live_validator/controller.py` — remove second `audit_objectives`
- Tests: `test_h682_report_reuse.py`, updated `test_h681_double_hierarchy_evaluate.py`

## Certification result

**PASS — commit eligible**
