# Sprint H-6.9.3 — Diagnostic Representation Certification Plan

**Status: CERTIFICATION CONTRACT (FROZEN)**  
**Scope: Alternative E (split frame fields) + summary-default logger policy (H-6.9.2)**  
**Implementation: FORBIDDEN until this contract is marked READY and an implementation sprint is opened.**

This document defines pass/fail gates only. It does not authorize code changes.

---

## 1. Architecture contract (frozen)

### 1.1 Roles

| Artifact | Role | Consumers |
|----------|------|-----------|
| `ObjectiveAuditReport` (runtime report **R**) | Single source of truth for Objective **selection** (H-6.8.2) | Objective Engine; IDC detail; certification fingerprints for selection |
| Diagnostic log projection **P** | Presentation/log representation only | Snapshot Logger; IDC summary chrome |
| `ValidatorFrame` | Carrier of **R** and **P** for one observation tick | Controller → Logger / IDC |

### 1.2 Ownership

```
Hierarchy.evaluate → R
ObjectiveEngine selects using R only
Frame holds R (runtime) + P (derived, one-way)
SnapshotLogger serializes P for diagnostics (never R’s highs/lows tree as the diagnostic section)
IDC summary may use P; IDC detail may read R from latest frame only (no new evaluate)
```

### 1.3 Forbidden edges (absolute)

```
P ──✗──► R                          (projection must not reconstruct/replace runtime report)
P ──✗──► Hierarchy / Objective / Response / Continuation / Break
Logger ──✗──► mutate R
Logger ──✗──► serialize R as the diagnostic log body
IDC ──✗──► hierarchy.evaluate / audit_objectives for presentation
Derive(P) ──✗──► second hierarchy.evaluate
```

### 1.4 Allowed edge

```
R ──(pure, one-way, deterministic derive)──► P
```

Derive must be:

- Side-effect free on hierarchy, engines, checkpoints, journal
- Deterministic for identical **R**
- Invoked at most once per accepted tick on the live path (or equivalently cached on the frame for that tick only)

### 1.5 Untouched runtime surfaces

Implementation of Alternative E **must not** change behavior of:

- `PersistentStructuralHierarchy` evaluate / checkpoint / journal rules  
- Objective selection rules or inputs  
- Response / Continuation / Break evaluation  
- Checkpoint paths, fsync policy, version bump rules  
- Max `hierarchy.evaluate` per Tick ID (= 1) from H-6.8.2  

---

## 2. Certification matrix

Legend for each area: outcomes are only **PASS**, **FAIL**, or **UNKNOWN**.

| # | Area | PASS | FAIL | UNKNOWN |
|---|------|------|------|---------|
| 1 | Runtime correctness | Engine snapshots (Objective, Initiative, Response, Continuation, Break) **byte- or field-identical** to pre-change golden on fixed tick sequences; `decision == "DISABLED"` | Any engine snapshot differs; any engine throws new errors on golden | Incomplete golden set; non-deterministic clock not controlled |
| 2 | Selection correctness | Selected nearest eligible high/low (prices, strengths, persistence states) identical to pre-change; selection uses **R**, not **P** | Selection differs; code path reads **P** for selection | Ambiguous eligibility when fixtures lack majors |
| 3 | Checkpoint correctness | Hierarchy version sequence, journal length/sequence/causes, checkpoint write cadence (writes iff version changes) identical on golden | Version/journal/cadence diverge; extra/missing checkpoint files | Checkpoint path not configured in test |
| 4 | Logger correctness | Every NDJSON line validates against Schema Contract (§4); diagnostics section is **P** only; required fields present; forbidden fields absent | Missing required field; forbidden field present; diagnostics section is full **R** / contains `highs`+`lows` full arrays; schema version missing | Consumer tooling not updated (env issue) |
| 5 | IDC correctness | Summary renders from **P** without evaluate; detail (if shown) reads **R** from `latest` only; no `hierarchy.evaluate` during IDC render | IDC triggers evaluate/audit; detail invents data not in **R**; summary contradicts **P** | IDC page not exercised in CI |
| 6 | Projection correctness | **P** derived only from **R**; one-way; no mutation of **R**; `id(R)` unchanged across derive; probe shows ≤1 evaluate/tick | **P** feeds engines; **R** mutated by derive/logger; second evaluate; non-deterministic **P** for same **R** | Derive not instrumented |

**Overall certification:**  
**PASS** only if areas 1–6 are all **PASS**.  
Any **FAIL** → overall **FAIL**.  
Any **UNKNOWN** in 1–6 without a written waiver → overall **NOT READY** for implementation closeout (treat as blocking).

---

## 3. Area contracts (detailed PASS / FAIL / UNKNOWN)

### 3.1 Runtime correctness

**Prove:** Objective, Response, Continuation, Break (and Initiative as produced on the same path) are identical before vs after Alternative E on frozen fixtures.

| Result | Condition |
|--------|-----------|
| **PASS** | For each golden tick `i`: `frame.objective`, `frame.response`, `frame.continuation`, `frame.break_capability` (and `frame.initiative`) match pre-change baselines under controlled clock/tick_size/swings/price |
| **FAIL** | Any field-level mismatch, ordering change in engine outputs, or exception regression |
| **UNKNOWN** | Baseline not captured before implementation; clock/time nondeterminism not sealed |

### 3.2 Selection correctness

| Result | Condition |
|--------|-----------|
| **PASS** | Nearest eligible high/low selection identical; instrumentation or code review proves selection reads **R** / engine report only |
| **FAIL** | Selection differs; selection uses **P**; eligible set differs for same swings/price |
| **UNKNOWN** | Fixture has zero eligible majors (vacuous) |

### 3.3 Checkpoint correctness

| Result | Condition |
|--------|-----------|
| **PASS** | On identical tick streams: hierarchy `version` sequence identical; journal entries identical (sequence, swing_id, cause, old/new state fingerprints); checkpoint file write count and timing rule identical (write iff version delta) |
| **FAIL** | Extra/missing journal rows; version gaps/skips; checkpoint written when version unchanged; checkpoint skipped when version changed |
| **UNKNOWN** | No checkpoint path in test harness |

### 3.4 Logger correctness

| Result | Condition |
|--------|-----------|
| **PASS** | Schema §4 satisfied on every record; `diagnostic_log_version` present; diagnostics payload ≡ **P**; logger does not call `_jsonable(R)` for the diagnostic section |
| **FAIL** | See §7 Fail conditions (logger subset) |
| **UNKNOWN** | Log file empty because logger unbound |

### 3.5 IDC correctness

| Result | Condition |
|--------|-----------|
| **PASS** | H-6.8.1-style probe (or equivalent) shows **zero** `hierarchy.evaluate` during IDC render; summary consistent with **P**; detail consistent with **R** when detail is open |
| **FAIL** | Evaluate/audit during render; fabricated diagnostics |
| **UNKNOWN** | IDC not in automated suite |

### 3.6 Projection correctness

| Result | Condition |
|--------|-----------|
| **PASS** | Derive(R)→P pure; `hash(R before) == hash(R after)`; no writes to hierarchy; static/contract test that engines never accept **P** as audit report type for selection |
| **FAIL** | Mutation of **R**; reverse mapping used in runtime; non-determinism |
| **UNKNOWN** | No hash/identity probe around derive |

---

## 4. Schema contract — `diagnostic_log` (projection **P**)

### 4.1 Envelope

Every Snapshot Logger frame that includes diagnostics **must** embed:

```text
diagnostic_log_version: <uint>
diagnostic_log: <object>   # projection P
```

Field naming on `ValidatorFrame` may differ in implementation naming, but the **logged JSON** must expose version + projection object as specified here (implementation sprint maps names 1:1).

### 4.2 Versioning policy

| Rule | Definition |
|------|------------|
| Current version for E launch | **`diagnostic_log_version = 1`** |
| Increment when | Required field added/removed/renamed; semantics of a required field change; forbidden field becomes allowed (or reverse) in a breaking way |
| Non-increment when | Optional fields added; documentation-only clarifications |
| Unknown version | Logger consumers / cert harness → **FAIL** (do not silently interpret) |

### 4.3 Backward compatibility policy

| Version | Reader policy |
|---------|----------------|
| `1` | Only version defined in this contract |
| `< 1` | **FAIL** |
| `> 1` | **FAIL** until a new cert plan amends this document |

Writers must not emit multiple versions in one process without an explicit cert amendment.

### 4.4 Replay policy

| Mode | Policy |
|------|--------|
| Live IDC | May use **R** for detail; **P** for summary |
| NDJSON replay | Reconstructs **P** only; **must not** claim full `SwingDiagnostic` arrays unless a future version adds an explicit optional archive section |
| Golden replay | Compare engine outputs + checkpoint/journal + **P** fingerprint; do **not** require `fp(P) == fp(R)` |

### 4.5 Required fields (`diagnostic_log_version = 1`)

| Field | Type (logical) | Meaning |
|-------|----------------|---------|
| `diagnostic_log_version` | uint | Envelope version (=1) |
| `source` | string const | Must be `"objective_audit_report"` |
| `hierarchy_version` | int | Copied from **R** |
| `registry_size` | int | Copied from **R** |
| `transition_count` | int | Copied from **R** |
| `checkpoint_version` | int | Copied from **R** |
| `timestamp` | float | From **R** |
| `current_price` | float | From **R** |
| `tick_size` | float | From **R** |
| `high_count` | int | `len(R.highs)` |
| `low_count` | int | `len(R.lows)` |
| `eligible_high_count` | int | Count eligible in **R.highs** |
| `eligible_low_count` | int | Count eligible in **R.lows** |
| `challenged_count` | int | Count lifecycle CHALLENGED across highs+lows |
| `summary_line_count` | int | `len(R.summary_lines)` |
| `selected_high` | object\|null | Compact ref: `price`, `swing_id`, `lifecycle`, `eligible` for Objective-selected high if representable from **R**+frame.objective; else null with rule documented in impl sprint |
| `selected_low` | object\|null | Same for low |

> **Note:** Exact mapping from `frame.objective` → `selected_*` must preserve selection correctness tests; if a selected price cannot be matched to a row in **R**, field is `null` and cert logs **UNKNOWN** until fixture clarified—not silent invention.

### 4.6 Optional fields (v1)

| Field | Type | Meaning |
|-------|------|---------|
| `summary_lines_head` | list[str] | Prefix of `R.summary_lines` (max **32** lines) |
| `top_eligible_highs` | list[compact] | Top **K=5** eligible highs by existing sort order in **R** |
| `top_eligible_lows` | list[compact] | Top **K=5** eligible lows |
| `compact` row | object | `swing_id`, `price`, `lifecycle`, `category`, `eligible`, `distance_ticks`, `challenge_state` only |

### 4.7 Forbidden fields (v1) — logger diagnostics section

Must **not** appear under the diagnostic log object or as a substitute for it:

| Forbidden | Reason |
|-----------|--------|
| Full `highs` array of full `SwingDiagnostic` objects | H-6.9.1 hotspot; violates E |
| Full `lows` array of full `SwingDiagnostic` objects | Same |
| Embedding entire `ObjectiveAuditReport` as `objective_diagnostics` mirror with full collections | Same |
| Any mutable / engine handle / non-JSON-safe runtime object | Isolation |
| Fields that imply reverse derivation to mutate hierarchy | One-way rule |

**IDC detail** may still *display* full **R** from memory; that display is **not** the logger schema.

---

## 5. Fingerprint contract

Define three fingerprints (SHA-256 of canonical JSON with `sort_keys=True`, separators compact):

| ID | Subject | Canonical input |
|----|---------|-----------------|
| **FP-R** | Selection report | Full `_jsonable(R)` |
| **FP-P** | Diagnostic projection | Canonical JSON of **P** (schema v1) |
| **FP-S** | Snapshot payload diagnostics | The diagnostics object as written in the NDJSON line (must equal canonical **P**) |

### 5.1 Must match

| Pair | Rule |
|------|------|
| **FP-P** vs **FP-S** | **MUST match** on every logged tick |
| **FP-R** (pre) vs **FP-R** (post) | **MUST match** on golden runtime comparison ticks (selection report unchanged by derive/log) |
| Engine snapshot fingerprints | **MUST match** pre vs post (runtime correctness) |

### 5.2 Intentionally different

| Pair | Rule |
|------|------|
| **FP-R** vs **FP-P** | **MUST NOT** be required to match (by design of E) |
| **FP-R** vs **FP-S** | **MUST NOT** be required to match |

### 5.3 FAIL on fingerprints

- `FP-P != FP-S` → Logger correctness **FAIL**  
- `FP-R` changes across derive → Projection correctness **FAIL**  
- Requiring `FP-R == FP-P` in tests → plan violation (**FAIL** the test design, not the product)

---

## 6. Regression matrix (required tests)

Every row is **required** before Alternative E may be declared certified.

| ID | Test | Area | PASS criterion |
|----|------|------|----------------|
| T1 | Golden replay — engine outputs | Runtime / Selection | Pre/post identical Objective/Response/Continuation/Break/Initiative on frozen ticks |
| T2 | Golden replay — checkpoint/journal | Checkpoint | Version + journal identical |
| T3 | Live replay — accept ticks from NDJSON ingress | Runtime / Logger | Engines stable; logs schema-valid |
| T4 | Stress replay — ≥500 ticks | Runtime / Checkpoint / Logger | No evaluate>1/tick; no schema FAIL; no crash |
| T5 | Large swing collections (≥20 highs + ≥20 lows) | Projection / Logger | **P** omits full arrays; logger time regression vs baseline optional evidence only (not a FAIL gate unless schema violated) |
| T6 | Empty collections (no swings) | Projection / Logger | Required fields present; counts 0; selected nulls |
| T7 | Challenge transitions | Selection / Checkpoint / Projection | Selection+journal match baseline; `challenged_count` reflects **R** |
| T8 | One-way projection probe | Projection | **R** hash stable across derive; engines never typed on **P** |
| T9 | No second evaluate | Runtime (H-6.8.2) | Max evaluate/Tick ID = 1 with logger+IDC render |
| T10 | Logger forbidden-field scan | Logger | No full `highs`/`lows` SwingDiagnostic arrays in diagnostic section |
| T11 | FP-P == FP-S | Logger / Fingerprints | Match every logged tick |
| T12 | FP-R pre == FP-R post (goldens) | Selection / Projection | Match |
| T13 | IDC render probe | IDC | Zero evaluate during Performance/Objective IDC pages |
| T14 | Schema version gate | Logger | Missing/wrong `diagnostic_log_version` → FAIL |

**Golden replay:** locked fixtures + expected digests checked into the implementation sprint (not this plan).  
**Live replay:** ingress file of recorded ticks.  
**Stress replay:** synthetic or recorded long stream (≥500).

---

## 7. Fail conditions (hard)

Any one ⇒ certification **FAIL** (implementation must not ship):

1. Missing required schema field  
2. Projection mutates runtime report **R** or hierarchy state  
3. Different Objective selection vs pre-change golden  
4. Different Response / Continuation / Break vs golden  
5. Different checkpoint version sequence  
6. Different journal (content or cadence)  
7. Second `hierarchy.evaluate` per accepted Tick ID  
8. Logger serializes full runtime report collections (`highs`/`lows` full diagnostics) as the diagnostic log body  
9. `FP-P != FP-S`  
10. IDC or logger path calls `audit_objectives` / `hierarchy.evaluate` for presentation  
11. Projection used as input to Objective selection  
12. Emit `diagnostic_log_version` ≠ 1 without amending this contract  

---

## 8. Implementation gate checklist

Implementation sprint **may not start** until all boxes are acknowledged.

- [ ] H-6.9.2 Alternative E accepted as scope  
- [ ] This H-6.9.3 contract reviewed (runtime / logger / IDC owners)  
- [ ] Schema v1 required/optional/forbidden lists accepted  
- [ ] Fingerprint match/differ rules accepted  
- [ ] Regression matrix T1–T14 accepted as minimum  
- [ ] Explicit waiver list empty (or written waivers for UNKNOWN-only items)  
- [ ] Agreement: **FP-R need not equal FP-P**  
- [ ] Agreement: checkpoints/engines untouched  
- [ ] Agreement: no optimization work conflated with representation change  

Implementation sprint **may not close / CERTIFY** until:

- [ ] Areas 1–6 all **PASS**  
- [ ] T1–T14 all **PASS**  
- [ ] No hard fail condition triggered  
- [ ] Certification registry updated (separate doc sprint)  

---

## 9. Final gate statement

### Contract completeness

All requested certification areas, PASS/FAIL/UNKNOWN rules, schema versioning, fingerprints, regression tests, and fail conditions are specified above for Alternative E.

### Readiness for implementation

# READY

This certification contract is **READY** to gate an implementation sprint.  
**No implementation is authorized by this document itself**—only by a subsequent sprint that cites **H-6.9.3 READY** and executes the matrix without weakening FAIL conditions.
