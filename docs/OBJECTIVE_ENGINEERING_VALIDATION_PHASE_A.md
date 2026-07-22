# Objective Engine V2 — Engineering Validation Phase A

**Status:** Tooling / workflow (not Formal Validation, not Certification)  
**Resume point:** H-6.9.4 Alternative E PASS  
**Engine:** CALIBRATED Objective Engine V2 (O-1 / O-2) — **unchanged**

---

## Purpose

Verify Objective Engine behavior on **live market** evidence **before** Formal Live Validation.

| This phase does | This phase does **not** |
|-----------------|-------------------------|
| Collect HIGH / LOW / persistence / changes | Advance registry to VALIDATED |
| Infer replace / breach reason classes | Recalibrate or change thresholds |
| Highlight anomalies immediately | Certify the module |
| One (or more) engineering live sessions | UI / Mission Control / Observation product work |

---

## Absolute bans

- No Objective algorithm changes  
- No recalibration / threshold changes  
- No Formal Validation claim from this phase alone  
- No Mission Control / Dashboard / Terminal Display / Observation / Replay feature work  

---

## What is collected (every evaluate)

| Field | Source |
|-------|--------|
| Timestamp | `ObjectiveSnapshot.timestamp` |
| Current price | `ObjectiveSnapshot.current_price` |
| Objective HIGH price / distance / strength | snapshot |
| Objective LOW price / distance / strength | snapshot |
| Persistence HIGH / LOW | `high_state` / `low_state` |
| Change flag + change kind | edge vs prior sample |
| Replace reason | inferred (see below) |
| Breach reason | inferred (see below) |

### Reason classes (observation only — not engine API)

| Persistence state | Reason class |
|-------------------|--------------|
| `NEW` | `FIRST_ASSIGNMENT` |
| `PERSISTED` | `UNCHANGED` |
| `REPLACED` | `NEARER_ELIGIBLE` (expected) or `UNEXPECTED_NOT_NEARER` (anomaly) |
| `BREACHED` | `CONFIRMED_BROKEN` |
| `SUPERSEDED` | `LIFECYCLE_SUPERSEDED` |
| cleared without breach/supersede | `CLEARED_UNEXPLAINED` (anomaly candidate) |

---

## Anomalies (highlight immediately)

| Code | Meaning |
|------|---------|
| `UNEXPECTED_REPLACEMENT` | `REPLACED` but new distance ≥ previous distance |
| `SIDE_COUPLING` | Both sides change identity on one evaluate while both prior states were `PERSISTED` and neither transition is `BREACHED`/`SUPERSEDED` |
| `UNEXPLAINED_FLICKER` | Side identity A→B→A within ≤3 evaluates without breach/supersede justification |
| `INVALID_NONE` | Price `None` with active persistence state, or price set with impossible null state pairing |
| `IMPOSSIBLE_TRANSITION` | Illegal persistence transition (e.g. `None`→`REPLACED`, `None`→`BREACHED`, `BREACHED` with price retained) |

Anomalies are **findings**, not Formal Validation FAIL. They guide early bug hunt.

---

## How to run one live session

```bash
# From HOTIRJAM_AI_5 (editable install recommended)
hotirjam-ai5-objective-ev \
  --out-dir logs/objective_ev/session_$(date +%Y%m%d) \
  --max-seconds 3600
```

Optional: `--tick-file /path/to/mnq_ticks.ndjson`, `--max-samples N`, `--symbol MNQ`.

Outputs under `--out-dir`:

- `samples.ndjson` — every evaluate sample  
- `changes.ndjson` — identity or persistence-state edges  
- `anomalies.ndjson` — anomaly records (also printed to stderr immediately)  
- `session_report.txt` — engineering summary (not a certification)

---

## PASS / FAIL (Phase A workflow)

| Gate | Meaning |
|------|---------|
| **PASS** | Unit tests for recorder / anomalies / CLI wiring pass; no Objective logic diffs; package usable for a live session |
| **FAIL** | Tests fail, or Objective engine files were modified |

Formal VALIDATED criteria are **out of scope** for Phase A (see Live Validation methodology).

---

## Next after Phase A

1. Run ≥1 live session; triage anomalies.  
2. If bugs confirmed → audit sprint (evidence) before any code fix.  
3. If clean enough → Formal Live Validation (CALIBRATED → VALIDATED).  
